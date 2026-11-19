# Assistente de configuração — passo 4: descobrir o ambiente

O ProxOrchestrator consulta o seu cluster Proxmox pela API e mostra o que encontrou. Esta página é só para conferir — nada é alterado no seu ambiente Proxmox.

## O que foi descoberto

### Nós do cluster

Todos os nós do cluster Proxmox aparecem, com o estado online/offline. O ProxOrchestrator pode criar VMs em qualquer nó online. No passo 5 você escolhe um nó padrão.

### Pools de armazenamento

Cada pool mostra:
- **Nome** — o ID do armazenamento usado nos comandos do Proxmox
- **Tipo** — `dir` (pasta), `lvm`, `lvmthin`, `zfspool`, `nfs`, `cifs` etc.
- **Espaço disponível** — espaço livre em GB. Fica em laranja quando está abaixo de 50 GB.
- **Compartilhado** — se o armazenamento é acessível por todos os nós do cluster (importante para migração)

Ao escolher um pool para importar VMs, prefira os que têm espaço livre suficiente. A imagem qcow2 importada precisa caber junto com as outras VMs.

### Bridges de rede

As bridges Linux do host Proxmox onde as VMs podem ser ligadas. Normalmente:
- `vmbr0` — a bridge principal, em geral ligada à placa de rede física
- Bridges adicionais para VLANs ou redes isoladas

### VMs existentes

Se o ProxOrchestrator encontrou VMs, os VMIDs delas são anotados para você evitar conflitos ao definir a faixa de VMIDs no passo 5.

## O que fazer se algo parecer errado

**Falta um pool de armazenamento** — se você esperava ver um pool, confira se ele está ativado e acessível no Proxmox (Datacenter → Storage). Montagens NFS/CIFS precisam estar montadas e funcionando.

**Nó aparece "offline"** — é um problema real do cluster. Confira o nó na interface web do Proxmox e resolva a comunicação do cluster antes de continuar.

**Nenhuma bridge encontrada** — é incomum. Confira se o nó Proxmox tem pelo menos uma bridge Linux configurada (o Proxmox cria a `vmbr0` por padrão).

**A descoberta falhou por completo** — normalmente significa que o token da API não tem as permissões certas (confira os comandos do passo 3) ou que a API ficou inacessível. Volte ao passo 3 e verifique o token.
