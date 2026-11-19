# Permissões do Proxmox

Os usuários, grupos e permissões **do Proxmox** (Datacenter → Permissions),
não as contas do ProxOrchestrator (essas ficam em *Conta → Usuários*).
Só os administradores do ProxOrchestrator podem abrir esta página.

- **Usuários**: realm, ativo, validade, nome, e-mail, grupos e tokens da API
  (os tokens de outros usuários só aparecem quando o token da API pode vê-los).
- **Grupos** e os membros de cada um.
- **Permissões**: a ACL — qual usuário, grupo ou token tem qual função em
  qual caminho (`/`, `/vms/100`, `/storage/local`…). *Propagar* significa que a
  função também vale abaixo desse caminho.
- **Funções**: funções embutidas e personalizadas, com os privilégios delas.
- **Pools**: pools de recursos e os membros deles.
- **Realms**: origens de autenticação (PAM, Proxmox VE, LDAP, OpenID…).

Use esta página para conferir o que o token do ProxOrchestrator
(`proxorchestrator@pve!app`) pode fazer. Alterar usuários e ACLs exige
`User.Modify` / `Permissions.Modify`; faça isso na interface do Proxmox.
