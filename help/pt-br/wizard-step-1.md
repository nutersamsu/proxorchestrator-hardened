# Assistente de configuração — passo 1: host Proxmox

Este passo define os dados de conexão do seu servidor Proxmox VE.

## O que preencher

**Host do Proxmox** — o endereço IP ou o nome do seu servidor Proxmox VE. Ele precisa ser alcançável a partir do servidor onde roda o ProxOrchestrator. Exemplos:
- `192.168.1.100`
- `proxmox.minhaempresa.com`
- `pve-node1.local`

**Porta SSH** — a porta em que o SSH do Proxmox escuta. O padrão é `22`. Só mude se você configurou uma porta SSH diferente no host Proxmox.

**Porta da API** — a porta em que a API web do Proxmox escuta. O padrão é `8006`. É a mesma porta que você usa para abrir a interface web do Proxmox.

## O que acontece ao clicar em "Testar e continuar"

O ProxOrchestrator vai:
1. Tentar uma conexão TCP na porta SSH para ver se ela está acessível
2. Tentar uma conexão TCP na porta da API para ver se o Proxmox responde
3. Salvar esses dados na configuração se as duas funcionarem

O teste **não** pede credenciais neste passo — ele só verifica a conexão de rede.

## Requisitos de rede

- O servidor do ProxOrchestrator precisa alcançar o host Proxmox nas duas portas
- Se usar um nome, o DNS precisa resolvê-lo corretamente a partir do servidor do ProxOrchestrator
- Os firewalls entre os dois servidores precisam permitir conexões de saída nas portas 22 e 8006

## Problemas comuns

**"Connection refused"** — o servidor responde, mas a porta não está escutando. Confira se os números das portas estão certos e se o SSH (`sshd`) e a API do Proxmox estão rodando.

**"Network unreachable" ou tempo esgotado** — o servidor do ProxOrchestrator não alcança o host Proxmox. Confira rotas, firewalls e VLANs entre os dois servidores.

**O nome não resolve** — tente usar o endereço IP. Ou confira se o DNS está bem configurado no servidor do ProxOrchestrator (`/etc/resolv.conf`).

**Atrás de NAT** — se o host Proxmox estiver atrás de NAT, você vai precisar de redirecionamento das portas 22 e 8006 para o servidor Proxmox.
