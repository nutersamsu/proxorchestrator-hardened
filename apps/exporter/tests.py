"""Download-once and expiry of export packages (.px)."""

import os
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import UserProfile
from apps.exporter.models import ExportJob, LxcExportJob
from apps.wizard.models import ProxmoxConfig


class ExportDownloadTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.user = User.objects.create_user("admin", password="S3cure-pass-for-tests!")
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        UserProfile.objects.update_or_create(user=self.user, defaults={"must_change_password": False})
        ProxmoxConfig.objects.create(host="192.0.2.10", is_configured=True, wizard_step=6,
                                     default_node="pve")
        self.client = Client()
        self.client.force_login(self.user)

    def _package(self, name="1.px", size=3 * 1024 * 1024 + 17):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(os.urandom(size))
        return path, size

    def _job(self, model=ExportJob, delete=True, **kw):
        path, size = self._package(f"{model.__name__}-{delete}.px")
        job = model.objects.create(vmid=103, node="pve", stage="DONE", output_path=path,
                                   delete_after_download=delete, **kw)
        return job, path, size

    def _url(self, job):
        name = "export_download" if isinstance(job, ExportJob) else "lxc_export_download"
        return reverse(name, args=[job.pk])

    def test_complete_download_removes_package(self):
        job, path, size = self._job(vm_name="xpenology-teste")
        r = self.client.get(self._url(job))
        self.assertEqual(r["Content-Length"], str(size))
        self.assertEqual(r["X-Accel-Buffering"], "no")
        self.assertIn('filename="xpenology-teste-103.px"', r["Content-Disposition"])
        body = b"".join(r.streaming_content)
        self.assertEqual(len(body), size)
        job.refresh_from_db()
        self.assertIsNotNone(job.downloaded_at)
        self.assertEqual(job.output_path, "")
        self.assertFalse(os.path.exists(path))

    def test_interrupted_download_keeps_package(self):
        job, path, _size = self._job()
        r = self.client.get(self._url(job))
        it = iter(r.streaming_content)
        next(it)          # first chunk only, then the browser goes away
        r.close()
        job.refresh_from_db()
        self.assertIsNone(job.downloaded_at)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(job.output_path, path)

    def test_keep_option_leaves_package(self):
        job, path, _size = self._job(delete=False)
        b"".join(self.client.get(self._url(job)).streaming_content)
        job.refresh_from_db()
        self.assertIsNotNone(job.downloaded_at)
        self.assertTrue(os.path.exists(path))

    def test_lxc_download_removes_package(self):
        job, path, _size = self._job(model=LxcExportJob, ct_name="web")
        b"".join(self.client.get(self._url(job)).streaming_content)
        self.assertFalse(os.path.exists(path))

    def test_second_download_after_removal_is_404(self):
        job, _path, _size = self._job()
        b"".join(self.client.get(self._url(job)).streaming_content)
        self.assertEqual(self.client.get(self._url(job)).status_code, 404)

    def test_done_page_explains_removal(self):
        job, _path, _size = self._job(vm_name="xpenology-teste")
        html = self.client.get(reverse("export_progress", args=[job.pk])).content.decode()
        self.assertIn("removed from this server as soon as the download completes", html)
        b"".join(self.client.get(self._url(job)).streaming_content)
        html = self.client.get(reverse("export_progress", args=[job.pk])).content.decode()
        self.assertIn("was downloaded on", html)
        self.assertNotIn("Download .px Package", html)

    def test_trigger_stores_choice(self):
        with mock.patch("apps.exporter.tasks.run_export_pipeline.delay"):
            self.client.post(reverse("export_trigger", args=[103]), {"export_mode": "live"})
            self.assertFalse(ExportJob.objects.get(vmid=103).delete_after_download)
            ExportJob.objects.all().delete()
            self.client.post(reverse("export_trigger", args=[103]),
                             {"export_mode": "live", "delete_after_download": "on"})
            self.assertTrue(ExportJob.objects.get(vmid=103).delete_after_download)

    def test_options_page_asks_by_default(self):
        with mock.patch.object(ProxmoxConfig, "get_api_client", side_effect=Exception("offline")):
            html = self.client.get(reverse("export_options", args=[103])).content.decode()
        self.assertIn('name="delete_after_download"', html)
        self.assertNotIn('name="delete_after_download" checked', html)
        self.assertFalse(ExportJob._meta.get_field("delete_after_download").default)

    def test_after_download_offers_delete_now_or_keep(self):
        job, path, _size = self._job(delete=False, vm_name="xpenology-teste")
        state = reverse("export_download_state", args=[job.pk])
        self.assertEqual(self.client.get(state).json(), {"downloaded_at": "", "file": True})
        b"".join(self.client.get(self._url(job)).streaming_content)
        self.assertTrue(self.client.get(state).json()["downloaded_at"])
        html = self.client.get(reverse("export_progress", args=[job.pk])).content.decode()
        self.assertIn("Download finished on", html)
        self.assertIn("Delete from server now", html)
        self.assertIn("Keep until", html)
        self.assertIn("deleted automatically on", html)
        r = self.client.post(reverse("export_delete_package", args=[job.pk]))
        self.assertRedirects(r, reverse("export_progress", args=[job.pk]), fetch_redirect_response=False)
        self.assertFalse(os.path.exists(path))
        job.refresh_from_db()
        self.assertEqual(job.output_path, "")
        self.assertTrue(ExportJob.objects.filter(pk=job.pk).exists())
        html = self.client.get(reverse("export_progress", args=[job.pk])).content.decode()
        self.assertIn("removed from this server", html)
        self.assertNotIn("Delete from server now", html)

    def test_lxc_delete_package_endpoint(self):
        job, path, _size = self._job(model=LxcExportJob, delete=False, ct_name="web")
        self.client.post(reverse("lxc_export_delete_package", args=[job.pk]))
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.client.get(reverse("lxc_export_download_state", args=[job.pk])).json()["file"], False)

    def test_delete_package_requires_post(self):
        job, path, _size = self._job(delete=False)
        self.assertEqual(self.client.get(reverse("export_delete_package", args=[job.pk])).status_code, 405)
        self.assertTrue(os.path.exists(path))


class ExportExpiryTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _old_job(self, model, hours_old):
        path = os.path.join(self.tmp.name, f"{model.__name__}-{hours_old}.px")
        open(path, "wb").close()
        job = model.objects.create(vmid=1, node="pve", stage="DONE", output_path=path)
        model.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(hours=hours_old))
        return job, path

    @override_settings(EXPORT_RETENTION_HOURS=6)
    def test_cleanup_uses_retention_setting(self):
        from apps.exporter.tasks import cleanup_old_exports, cleanup_old_lxc_exports
        old, old_path = self._old_job(ExportJob, 7)
        new, new_path = self._old_job(ExportJob, 5)
        lxc_old, lxc_path = self._old_job(LxcExportJob, 7)
        self.assertEqual(cleanup_old_exports(), 1)
        self.assertEqual(cleanup_old_lxc_exports(), 1)
        self.assertFalse(os.path.exists(old_path))
        self.assertFalse(os.path.exists(lxc_path))
        self.assertTrue(os.path.exists(new_path))
        self.assertTrue(ExportJob.objects.filter(pk=new.pk).exists())

    def test_cleanup_is_scheduled(self):
        from proxorchestrator.celery import app
        tasks = {e["task"] for e in app.conf.beat_schedule.values()}
        self.assertIn("exporter.cleanup_old_exports", tasks)
        self.assertIn("exporter.cleanup_old_lxc_exports", tasks)

    @override_settings(EXPORT_RETENTION_HOURS=48)
    def test_expires_at_follows_setting(self):
        job, _ = self._old_job(ExportJob, 0)
        job.refresh_from_db()
        self.assertAlmostEqual((job.expires_at - job.updated_at).total_seconds(), 48 * 3600)
