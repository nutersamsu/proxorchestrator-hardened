# Exportação de VM (fase 2)

A exportação de VMs está planejada para a fase 2 do desenvolvimento do ProxOrchestrator. Esta página descreve o que o recurso vai fazer.

## O que é a exportação de VM?

A exportação de VM permite empacotar uma VM do Proxmox (a imagem de disco e a configuração) num arquivo portátil que pode ser:
- Guardado como backup, sem depender do backup embutido do Proxmox
- Compartilhado com outra equipe ou empresa
- Importado em outro servidor Proxmox pela importação do ProxOrchestrator
- Enviado para armazenamento de objetos na nuvem (S3, Azure Blob etc.)
- Convertido para o formato de outro hipervisor (VMware, Hyper-V)

## Recursos planejados

### Pacotes portáteis
Exportar qualquer VM como um arquivo compactado e versionado, com a imagem de disco qcow2 e um arquivo JSON de metadados com a configuração completa da VM. Esses pacotes `.proxorchestrator` podem ser importados em qualquer instância do ProxOrchestrator.

### Opções de formato
Escolha o formato dos discos exportados:
- `qcow2` — nativo, compactado, o melhor para importar de novo
- `vmdk` — para importar no VMware ESXi ou Workstation
- `raw` — máxima compatibilidade, o maior arquivo
- `vhd`/`vhdx` — para importar no Hyper-V

### Exportar para a nuvem
Envio direto dos pacotes exportados para armazenamento de objetos na nuvem:
- Amazon S3 e armazenamentos compatíveis com S3 (MinIO, Wasabi, Backblaze B2)
- Bucket, prefixo/caminho e classe de armazenamento configuráveis
- Envio em várias partes para imagens de disco grandes

### Exportações criptografadas
Criptografia AES-256-GCM opcional dos pacotes exportados, com senha ou arquivo de chave. Protege dados sensíveis das VMs guardados em armazenamento não confiável.

### Exportar snapshots
Exportar a partir de um snapshot específico do Proxmox em vez do estado atual do disco, para ter uma cópia boa de um momento sem desligar a VM.

### Exportações agendadas
Configurar jobs de exportação recorrentes para guardar VMs escolhidas no armazenamento local ou na nuvem, num horário definido.

## Alternativa atual

Até a fase 2 sair, você pode exportar VMs manualmente com as ferramentas do Proxmox:

**Para backup local:**
```
vzdump {vmid} --dumpdir /caminho/do/backup --mode snapshot
```

**Para exportar o disco:**
```
qemu-img convert -O vmdk /var/lib/vz/images/{vmid}/vm-{vmid}-disk-0.qcow2 saida.vmdk
```

## Ajude a definir a fase 2

O ProxOrchestrator é de código aberto e feito pela comunidade. Se a exportação de VMs é importante para você:
1. Dê uma estrela no projeto no [GitHub](https://github.com/ForgedIO/ProxOrchestrator)
2. Abra um pedido de recurso descrevendo o seu caso
3. Pense em contribuir — o código é Django + Celery, contribuições são bem-vindas

A sua opinião influencia diretamente a prioridade do desenvolvimento.
