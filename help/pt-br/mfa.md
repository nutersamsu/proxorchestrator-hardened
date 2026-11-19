# Autenticação multifator (MFA)

## Visão geral

O MFA acrescenta uma segunda camada de segurança à sua conta no ProxOrchestrator. Depois da senha, é pedido um código de 6 dígitos de um aplicativo autenticador.

## Configurar o MFA

1. Vá em **Configuração do MFA** (ou você será redirecionado, se o MFA for obrigatório)
2. Leia o QR code com o seu aplicativo autenticador (Google Authenticator, Authy, Microsoft Authenticator)
3. Digite o código de 6 dígitos do aplicativo para verificar
4. **Guarde os códigos de recuperação** — são códigos de uso único para o caso de você perder o aparelho

## Entrar com MFA

1. Digite usuário/e-mail e senha normalmente
2. Será pedido o código de 6 dígitos do autenticador
3. Digite o código do aplicativo — ele muda a cada 30 segundos

## Opções de recuperação

Se você perder o acesso ao aplicativo autenticador:

- **Códigos de recuperação** — digite um dos 8 códigos guardados na configuração (cada um vale uma vez)
- **Recuperação por e-mail** — clique em "Enviar um código de recuperação por e-mail" para receber um código de uso único (exige o e-mail configurado)
- **Redefinição pelo administrador** — um administrador pode redefinir o seu MFA na página de gerenciamento de usuários

## Exigência para todos

Os administradores podem obrigar todos os usuários locais e LDAP a configurar o MFA. Quando isso está ativo:
- Usuários novos são levados à configuração do MFA depois do primeiro login
- Os usuários não podem desativar o MFA
- Usuários do Entra ID (Azure AD) ficam de fora — o MFA deles é tratado pelo provedor de identidade

## Desativar o MFA

Se o MFA não for obrigatório para todos, você pode desativá-lo na página de configuração do MFA. É preciso confirmar com a sua senha.

## Observações importantes

- **Usuários do Entra ID** — o MFA é gerenciado pelo locatário do Azure AD, não pelo ProxOrchestrator
- **Usuários do LDAP** — o MFA do ProxOrchestrator é separado de qualquer MFA do servidor de diretório
- Os códigos de recuperação aparecem **uma vez só**, na configuração — guarde-os na hora
- Cada código de recuperação só pode ser usado **uma vez**
