# Inventário de contêineres

O inventário mostra todos os contêineres LXC do nó Proxmox conectado. Os dados vêm ao vivo da API do Proxmox toda vez que a página é aberta ou atualizada.

## Entendendo a tabela

**CTID** — o número único que o Proxmox dá ao contêiner.

**Nome** — o nome do host do contêiner. Clique para abrir a página de detalhes.

**Estado** — situação atual:
- Verde "Rodando" — o contêiner está ligado
- Vermelho "Parado" — o contêiner está desligado

**CPU** — nos contêineres rodando, mostra o uso de CPU em porcentagem. Nos parados, mostra quantos núcleos estão configurados.

**RAM** — a memória máxima do contêiner.

**Tempo ligado** — há quanto tempo o contêiner está rodando (só nos que estão rodando).

**Nó** — em qual nó do cluster Proxmox o contêiner está.

## Ações de energia

As ações aparecem conforme o estado do contêiner:

**Contêineres rodando:**
- **Desligar** — desligamento normal pelo sistema de inicialização do contêiner. O sistema convidado arruma tudo e desliga.
- **Forçar parada** — mata o processo do contêiner na hora, como puxar o fio da tomada. Use só como último recurso em contêineres travados. Pode perder dados se o contêiner estava gravando em disco.
- **Reiniciar** — reinício normal.

**Contêineres parados:**
- **Iniciar** — liga o contêiner.

As ações usam HTMX para atualizar só a linha da tabela, sem recarregar a página. A linha mostra o novo estado em poucos segundos.

## Console

Os contêineres rodando têm um botão Console, que abre uma sessão de terminal noVNC interativa em outra aba. O console passa pelo nginx até o websocket VNC do Proxmox.

## Filtro e busca

Use a caixa de busca no cabeçalho da tabela para filtrar por nome ou CTID. O filtro é feito no navegador e é instantâneo — não precisa consultar o servidor.

## Atualização automática

A tabela de contêineres se atualiza sozinha a cada 10 segundos para manter o estado em dia. Também há um botão Atualizar no cabeçalho da página.

## Scripts da comunidade

Quer implantar um app pronto como Docker, Pi-hole ou Home Assistant? Abra **Scripts da comunidade** na barra lateral ou na página Novo contêiner. Veja mais de 680 scripts da comunidade e implante com um clique. Detalhes na [ajuda dos scripts da comunidade](/help/lxc-community-scripts/).

## Problemas comuns

**A tabela mostra erro ou está vazia** — a API do Proxmox pode estar fora do ar por um momento. Confira o estado da API no painel. Tente atualizar.

**O botão de ação não responde** — a chamada à API pode ter falhado. Confira se o token da API ainda é válido (tokens do Proxmox podem expirar ou ser revogados). Deve aparecer um aviso se a ação falhar.

**O contêiner mostra o estado errado** — o estado mostrado era o certo na última atualização. Clique em Atualizar para ver os dados atuais. Mudanças feitas pela própria interface do Proxmox só aparecem aqui na próxima atualização automática.
