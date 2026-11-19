# Backups

Os backups são arquivos **vzdump** do Proxmox (`vzdump-qemu-…` para VMs,
`vzdump-lxc-…` para contêineres) guardados em armazenamentos que aceitam o
tipo de conteúdo *backup*.

## Jobs de backup

Os jobs agendados de *Datacenter → Backup* no Proxmox: agendamento, próxima
execução, quais convidados, armazenamento, modo e retenção.

- **Executar agora** inicia o job na hora com as mesmas configurações, como na
  interface do Proxmox. O **hookscript** do job não roda desta forma: só o
  `root@pam` pode definir a opção `script`.
- Criar ou editar jobs exige o privilégio `Sys.Modify`. O token da API
  recomendado não tem, então os jobs ficam só para leitura aqui.

## Fazer backup agora

Escolha um ou mais convidados, um armazenamento, o modo e a compressão:

- **Snapshot**: o convidado continua rodando (recomendado).
- **Suspend**: o convidado fica pausado durante o backup.
- **Stop**: o convidado é desligado, copiado e ligado de novo.

As notas aceitam `{{guestname}}`, `{{vmid}}` e `{{node}}`. Um backup
**protegido** nunca é removido pelas regras de retenção e não pode ser
excluído até a proteção ser retirada.

As páginas de cada VM e contêiner também têm um cartão **Backup** com os
backups dele e um botão *Fazer backup agora*.

## Restaurar

A página de restauração mostra a configuração guardada no arquivo. Você pode:

- restaurar num **novo ID** (o padrão quando o convidado original ainda
  existe; marque *Único* para a cópia receber novos endereços MAC), ou
- **sobrescrever** o convidado original: marque *Sobrescrever* e digite o ID de
  novo. O convidado precisa estar parado; os discos atuais dele são destruídos.

Os discos vão para o armazenamento de onde vieram, a não ser que você escolha outro.

## Excluir

Para excluir, é preciso digitar o nome do arquivo. Backups protegidos precisam
ter a proteção retirada antes. O Proxmox deixa o token da API excluir um backup
quando ele tem `VM.Backup` naquele convidado e direito de alocar espaço no
armazenamento.
