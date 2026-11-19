# Recuperação de senha

## Requisitos

A recuperação de senha exige o **e-mail configurado** no ProxOrchestrator. Sem e-mail, os links de redefinição não podem ser enviados.

Para configurar o e-mail, vá em **Configurações > E-mail** e configure uma destas opções:
- **SMTP** — servidor de e-mail padrão
- **Microsoft Graph API** — Azure AD / Microsoft 365

## Como funciona

1. Clique em **"Esqueceu a senha?"** na página de login
2. Digite o e-mail associado à sua conta
3. Se existir uma conta local com esse e-mail, um link de redefinição é enviado para ele
4. Clique no link do e-mail para definir uma nova senha
5. O link expira em pouco tempo e só pode ser usado uma vez

## Observações importantes

- **Só contas locais** — usuários do LDAP e do Entra ID (Azure AD) gerenciam a senha pelo diretório deles. O link de redefinição não é enviado para essas contas.
- **Segurança** — a página sempre mostra a mesma mensagem de sucesso, exista ou não o e-mail, para ninguém descobrir quais contas existem.
- **Links expirados** — se um link expirou, você pode pedir outro na página de esqueci a senha.
