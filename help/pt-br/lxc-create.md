# Novo contêiner LXC — escolha do template

Este é o primeiro passo para criar um contêiner LXC. Escolha o template que servirá de base para o contêiner.

## Armazenamento de templates

Escolha um pool de armazenamento na lista. Só aparecem os pools com o tipo de conteúdo `vztmpl` ativado. Se nenhum aparecer, ative o tipo de conteúdo `vztmpl` em pelo menos um pool no Proxmox (Datacenter > Storage > escolha o pool > Edit > Content).

## Vendo os templates

### Baixados
Templates que já estão no seu nó Proxmox. Podem ser usados na hora, sem download. Clique num template para seguir para a configuração.

### Disponíveis para baixar
Mostra o catálogo oficial de templates do Proxmox (aplinfo). Ao escolher um, ele é baixado para o pool escolhido antes de continuar. Isso exige acesso à internet no nó Proxmox.

## Depois de escolher um template

Você vai para a página de configuração, onde define nome, recursos (CPU, RAM, swap), armazenamento, rede e autenticação do contêiner antes de a criação começar.

## Problemas comuns

**Nenhum pool de armazenamento na lista** — nenhum pool do seu nó Proxmox tem o tipo de conteúdo `vztmpl` ativado. Vá em Datacenter > Storage na interface web do Proxmox para configurar um.

**Nenhum template baixado** — você ainda não baixou nenhum template. Mude para a aba "Disponíveis para baixar" para ver e baixar do catálogo do Proxmox.

**Falha ao baixar o template** — o nó Proxmox pode estar sem acesso à internet. Baixe os templates manualmente e envie-os para um pool com `vztmpl` ativado.
