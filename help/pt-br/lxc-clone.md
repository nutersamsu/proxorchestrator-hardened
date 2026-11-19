# Clonar contêiner

Clonar cria uma cópia completa e independente de um contêiner LXC existente, com novo CTID e nome. O clone inclui o rootfs completo e toda a configuração.

## Opções de clonagem

### Geral
- **Novo nome do host** — nome do contêiner clonado. O padrão é o nome da origem com "-clone" no final.
- **CTID** — deixe em branco para usar o próximo ID livre, ou digite um número.

### Destino
- **Nó de destino** — em qual nó do cluster Proxmox criar o clone. O padrão é o mesmo nó da origem.
- **Armazenamento de destino** — pool de armazenamento do rootfs do clone. "O mesmo da origem" usa o pool do contêiner de origem.

## O que acontece na clonagem

1. **Snapshot** — se o contêiner de origem estiver rodando, um snapshot temporário é criado automaticamente (sem parada)
2. **Clonagem** — o Proxmox cria uma cópia completa do disco do contêiner
3. **Configuração** — o novo nome e a descrição são aplicados
4. **Início** — se o contêiner de origem estava rodando, o clone é ligado automaticamente
5. **Limpeza** — o snapshot temporário é removido do contêiner de origem

O clone é totalmente independente — não depende da origem. Depois você pode alterar ou excluir qualquer um dos dois.

## Depois de clonar

O contêiner clonado herda a configuração de rede da origem. Se a origem usa IP fixo, mude o endereço IP do clone no Proxmox para evitar conflitos na rede.

## Problemas comuns

**A clonagem falha com erro de armazenamento** — o pool de destino pode não ter espaço livre suficiente ou não aceitar o tipo de conteúdo necessário para contêineres.

**A clonagem demora muito** — contêineres com rootfs grande levam mais tempo para copiar. A página de andamento continua consultando até a clonagem terminar.

**Conflito de rede depois de clonar** — se a origem e o clone tiverem o mesmo IP fixo, um deles não vai conseguir se conectar. Mude a configuração de rede do clone no Proxmox.
