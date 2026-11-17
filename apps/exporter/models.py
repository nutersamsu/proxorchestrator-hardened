import json
import logging
import os
from datetime import timedelta

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

def export_retention_hours():
    return int(getattr(settings, "EXPORT_RETENTION_HOURS", 24) or 24)


class DownloadableExportMixin:
    """Shared helpers for finished export packages (.px) kept on this server."""

    @property
    def file_available(self):
        return bool(self.stage == "DONE" and self.output_path and os.path.exists(self.output_path))

    @property
    def expires_at(self):
        """When the hourly cleanup removes a package that was not downloaded."""
        return self.updated_at + timedelta(hours=export_retention_hours())

    @property
    def retention_hours(self):
        return export_retention_hours()



class ExportJob(DownloadableExportMixin, models.Model):
    """Tracks a VM export pipeline job."""

    STAGE_QUEUED = "QUEUED"
    STAGE_READING_CONFIG = "READING_CONFIG"
    STAGE_SHUTTING_DOWN = "SHUTTING_DOWN"
    STAGE_EXPORTING_DISKS = "EXPORTING_DISKS"
    STAGE_BUILDING_MANIFEST = "BUILDING_MANIFEST"
    STAGE_PACKAGING = "PACKAGING"
    STAGE_DONE = "DONE"
    STAGE_FAILED = "FAILED"

    STAGE_CHOICES = [
        (STAGE_QUEUED, "Queued"),
        (STAGE_READING_CONFIG, "Reading Config"),
        (STAGE_SHUTTING_DOWN, "Shutting Down"),
        (STAGE_EXPORTING_DISKS, "Exporting Disks"),
        (STAGE_BUILDING_MANIFEST, "Building Manifest"),
        (STAGE_PACKAGING, "Packaging Archive"),
        (STAGE_DONE, "Done"),
        (STAGE_FAILED, "Failed"),
    ]

    vmid = models.IntegerField()
    node = models.CharField(max_length=100)
    vm_name = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default=STAGE_QUEUED)
    percent = models.IntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    vm_config_json = models.TextField(default="{}")
    output_path = models.CharField(max_length=1000, blank=True)
    delete_after_download = models.BooleanField(
        default=False,
        help_text="Remove the package without asking as soon as one download has completed.",
    )
    downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ExportJob(vm={self.vmid}, stage={self.stage})"

    @property
    def vm_config(self):
        try:
            return json.loads(self.vm_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_stage(self, stage, message="", percent=None):
        self.stage = stage
        self.message = message
        if percent is not None:
            self.percent = percent
        fields = ["stage", "message", "updated_at"]
        if percent is not None:
            fields.append("percent")
        self.save(update_fields=fields)
        logger.debug("ExportJob %d stage -> %s (%s)", self.pk, stage, message)


class PxImportJob(models.Model):
    """Tracks a .px package import pipeline job."""

    STAGE_QUEUED = "QUEUED"
    STAGE_TRANSFERRING = "TRANSFERRING"
    STAGE_CREATING_VM = "CREATING_VM"
    STAGE_IMPORTING_DISK = "IMPORTING_DISK"
    STAGE_CONFIGURING = "CONFIGURING"
    STAGE_CLOUD_INIT = "CLOUD_INIT"
    STAGE_STARTING = "STARTING"
    STAGE_CLEANUP = "CLEANUP"
    STAGE_DONE = "DONE"
    STAGE_FAILED = "FAILED"

    STAGE_CHOICES = [
        (STAGE_QUEUED, "Queued"),
        (STAGE_TRANSFERRING, "Transferring Disks"),
        (STAGE_CREATING_VM, "Creating VM"),
        (STAGE_IMPORTING_DISK, "Importing Disk"),
        (STAGE_CONFIGURING, "Configuring"),
        (STAGE_CLOUD_INIT, "Cloud-Init"),
        (STAGE_STARTING, "Starting"),
        (STAGE_CLEANUP, "Cleanup"),
        (STAGE_DONE, "Done"),
        (STAGE_FAILED, "Failed"),
    ]

    upload_path = models.CharField(max_length=1000)
    extract_dir = models.CharField(max_length=1000, blank=True)
    manifest_json = models.TextField(default="{}")
    vm_config_json = models.TextField(default="{}")
    vm_name = models.CharField(max_length=100, blank=True)
    vmid = models.IntegerField(null=True, blank=True)
    node = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default=STAGE_QUEUED)
    percent = models.IntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="px_import_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PxImportJob({self.vm_name}, {self.stage})"

    @property
    def vm_config(self):
        try:
            return json.loads(self.vm_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def manifest(self):
        try:
            return json.loads(self.manifest_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_stage(self, stage, message="", percent=None):
        self.stage = stage
        self.message = message
        if percent is not None:
            self.percent = percent
        fields = ["stage", "message", "updated_at"]
        if percent is not None:
            fields.append("percent")
        self.save(update_fields=fields)
        logger.debug("PxImportJob %d stage -> %s (%s)", self.pk, stage, message)


class LxcExportJob(DownloadableExportMixin, models.Model):
    """Tracks an LXC container export pipeline job."""

    STAGE_QUEUED = "QUEUED"
    STAGE_READING_CONFIG = "READING_CONFIG"
    STAGE_EXPORTING = "EXPORTING"
    STAGE_BUILDING_MANIFEST = "BUILDING_MANIFEST"
    STAGE_PACKAGING = "PACKAGING"
    STAGE_DONE = "DONE"
    STAGE_FAILED = "FAILED"

    STAGE_CHOICES = [
        (STAGE_QUEUED, "Queued"),
        (STAGE_READING_CONFIG, "Reading Config"),
        (STAGE_EXPORTING, "Exporting Container"),
        (STAGE_BUILDING_MANIFEST, "Building Manifest"),
        (STAGE_PACKAGING, "Packaging Archive"),
        (STAGE_DONE, "Done"),
        (STAGE_FAILED, "Failed"),
    ]

    vmid = models.IntegerField()
    node = models.CharField(max_length=100)
    ct_name = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default=STAGE_QUEUED)
    percent = models.IntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    ct_config_json = models.TextField(default="{}")
    output_path = models.CharField(max_length=1000, blank=True)
    delete_after_download = models.BooleanField(
        default=False,
        help_text="Remove the package without asking as soon as one download has completed.",
    )
    downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lxc_export_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LxcExportJob(ct={self.vmid}, stage={self.stage})"

    @property
    def ct_config(self):
        try:
            return json.loads(self.ct_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_stage(self, stage, message="", percent=None):
        self.stage = stage
        self.message = message
        if percent is not None:
            self.percent = percent
        fields = ["stage", "message", "updated_at"]
        if percent is not None:
            fields.append("percent")
        self.save(update_fields=fields)
        logger.debug("LxcExportJob %d stage -> %s (%s)", self.pk, stage, message)


class LxcPxImportJob(models.Model):
    """Tracks an LXC .px package import pipeline job."""

    STAGE_QUEUED = "QUEUED"
    STAGE_TRANSFERRING = "TRANSFERRING"
    STAGE_CREATING_CT = "CREATING_CT"
    STAGE_CONFIGURING = "CONFIGURING"
    STAGE_STARTING = "STARTING"
    STAGE_CLEANUP = "CLEANUP"
    STAGE_DONE = "DONE"
    STAGE_FAILED = "FAILED"

    STAGE_CHOICES = [
        (STAGE_QUEUED, "Queued"),
        (STAGE_TRANSFERRING, "Transferring Backup"),
        (STAGE_CREATING_CT, "Restoring Container"),
        (STAGE_CONFIGURING, "Configuring"),
        (STAGE_STARTING, "Starting"),
        (STAGE_CLEANUP, "Cleanup"),
        (STAGE_DONE, "Done"),
        (STAGE_FAILED, "Failed"),
    ]

    upload_path = models.CharField(max_length=1000)
    extract_dir = models.CharField(max_length=1000, blank=True)
    manifest_json = models.TextField(default="{}")
    ct_config_json = models.TextField(default="{}")
    ct_name = models.CharField(max_length=100, blank=True)
    vmid = models.IntegerField(null=True, blank=True)
    node = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default=STAGE_QUEUED)
    percent = models.IntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lxc_px_import_jobs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LxcPxImportJob({self.ct_name}, {self.stage})"

    @property
    def ct_config(self):
        try:
            return json.loads(self.ct_config_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def manifest(self):
        try:
            return json.loads(self.manifest_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_stage(self, stage, message="", percent=None):
        self.stage = stage
        self.message = message
        if percent is not None:
            self.percent = percent
        fields = ["stage", "message", "updated_at"]
        if percent is not None:
            fields.append("percent")
        self.save(update_fields=fields)
        logger.debug("LxcPxImportJob %d stage -> %s (%s)", self.pk, stage, message)
