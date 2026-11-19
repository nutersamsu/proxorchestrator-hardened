# Assistente de configuração — passo 3: token da API

O ProxOrchestrator conversa com o Proxmox VE pela API REST dele. Para isso é preciso um token da API — uma credencial separada da senha, criada no próprio Proxmox.

## Por que um token, e por que não o root?

Tokens da API são a forma recomendada de integrar com o Proxmox. Eles:
- Podem ser revogados a qualquer momento sem mudar a senha de ninguém
- Aparecem claramente nos logs de auditoria do Proxmox
- Podem ter privilégios limitados

Por segurança, o ProxOrchestrator **não** usa um token do `root@pam`. Ele usa um usuário próprio, `proxorchestrator@pve`, só com as funções de que precisa para gerenciar VMs e contêineres. Se o app for comprometido, o atacante não ganha controle total do host.

## Passo a passo

1. **Abra a interface web do Proxmox** em `https://SEU-HOST:8006` e vá em **o seu nó → Shell**

2. **Cole os comandos** mostrados nesta página (botão **Copiar comandos**). Eles:
   - criam o usuário `proxorchestrator@pve`
   - dão a ele as funções `PVEVMAdmin`, `PVEDatastoreUser` e `PVEAuditor` em `/`
   - dão `PVESDNUser` em `/sdn/zones/localnetwork` (necessário para ligar VMs às bridges no Proxmox 8/9)
   - criam o token `app` para esse usuário, com `--privsep 0` (o token herda exatamente as funções do usuário, nada além)

3. **Copie o segredo** — o último comando mostra uma tabela. Copie o valor da linha `value` (um UUID). É a única vez que o Proxmox mostra o segredo.

4. **Cole nesta página**:
   - ID completo do token: `proxorchestrator@pve!app`
   - Segredo do token: o UUID copiado

Se o usuário já existir, a primeira linha só avisa — tudo bem. No Proxmox 7, a linha do `/sdn/...` pode ser pulada.

## O que o token não pode fazer

De propósito, o token não tem `Sys.Modify`, `Sys.PowerMgmt`, `Sys.Syslog` nem `Datastore.Allocate`. Por isso algumas telas (nó, firewall do datacenter, jobs de backup, exclusão de ISOs) ficam só para leitura no ProxOrchestrator; essas coisas são feitas na interface do Proxmox.

## Formato do ID do token

O ID completo segue o formato `USUARIO@REALM!IDTOKEN`. Com os comandos acima:
- Usuário: `proxorchestrator@pve`
- ID do token: `app`

O ID completo fica: `proxorchestrator@pve!app`

## Problemas comuns

**"401 Unauthorized"** — o ID ou o segredo do token está errado. Os segredos são UUIDs no formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Confira se não há erro de digitação.

**"403 Forbidden"** — faltou alguma função. Confira se os comandos `pveum acl modify` rodaram sem erro, ou se o token foi criado com `--privsep 1` (nesse caso ele não herda as funções do usuário). Apague o token e crie de novo com `--privsep 0`.

**O segredo não foi guardado** — apague o token no Proxmox (`pveum user token remove proxorchestrator@pve app`, ou Datacenter → Permissions → API Tokens → Remove) e crie outro. O segredo não pode ser recuperado depois.

**API inacessível** — confira se a porta 8006 está acessível a partir do servidor do ProxOrchestrator (verificado no passo 1, mas às vezes os firewalls tratam as chamadas da API de outro jeito).
