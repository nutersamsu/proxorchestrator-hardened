# Configurações de autenticação — Microsoft Entra ID

O ProxOrchestrator aceita login único (SSO) com o Microsoft Entra ID (o antigo Azure Active Directory). Os usuários entram com as contas de trabalho ou escola da Microsoft pelo fluxo padrão OAuth2/OIDC.

## Como funciona a autenticação Entra ID

1. O usuário clica em "Entrar com a Microsoft" na página de login do ProxOrchestrator
2. O navegador vai para a página de login da Microsoft
3. O usuário se autentica com as credenciais da Microsoft (o MFA vale, se estiver configurado no locatário)
4. A Microsoft devolve o navegador ao ProxOrchestrator com um código de autorização
5. O ProxOrchestrator troca o código pelas informações de identidade do usuário
6. O ProxOrchestrator cria ou atualiza a conta local do usuário e faz o login

## Pré-requisitos

Você precisa de acesso ao portal do Microsoft Entra ID e permissão para criar App Registrations. Normalmente isso exige a função **Application Administrator** ou **Global Administrator** no locatário.

## Configurar o App Registration no Azure

### Passo 1: criar o App Registration
1. Abra o [portal.azure.com](https://portal.azure.com)
2. Vá em **Microsoft Entra ID** → **App registrations** → **New registration**
3. **Name:** ProxOrchestrator (ou outro nome descritivo)
4. **Supported account types:** escolha conforme a necessidade:
   - "Single tenant" — só os usuários da sua organização (o mais comum)
   - "Multi-tenant" — usuários de qualquer locatário Microsoft
5. **Redirect URI:** escolha "Web" e cole a URI mostrada na página de configurações do ProxOrchestrator

### Passo 2: pegar os IDs
Depois de criar o registro, a página Overview mostra:
- **Application (client) ID** — copie para o campo "ID do aplicativo (cliente)" do ProxOrchestrator
- **Directory (tenant) ID** — copie para o campo "ID do locatário (tenant)" do ProxOrchestrator

No campo do locatário, use o ID (GUID) ou o domínio principal da sua organização. Os valores `common`, `organizations` e `consumers` são recusados, porque deixariam qualquer conta Microsoft entrar.

### Passo 3: criar um client secret
1. Vá em **Certificates & secrets** na barra lateral esquerda
2. Clique em **New client secret**
3. Coloque uma descrição (ex.: "ProxOrchestrator") e uma validade
4. Clique em **Add**
5. **Copie a coluna "Value" na hora** — ela só aparece uma vez

Cole o valor do segredo no campo "Segredo do cliente" do ProxOrchestrator.

### Passo 4: permissões da API (opcional)
Para dar acesso de administrador por grupo, o ProxOrchestrator precisa ler a participação nos grupos. No App Registration:
1. Vá em **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**
2. Adicione `GroupMember.Read.All`
3. Clique em **Grant admin consent**

## Redirect URI

A redirect URI precisa ser exatamente igual à registrada no Azure. O ProxOrchestrator mostra a URI certa na página de configurações. Ela segue o formato:
`https://SEU-HOST/accounts/microsoft/login/callback/`

Se você mudar a porta ou o nome do ProxOrchestrator, precisa atualizar essa URI no Azure também.

## Domínios permitidos

Opcionalmente, limite o login a certos domínios de e-mail. Por exemplo, `contoso.com` faz só as contas Microsoft `@contoso.com` poderem entrar. Deixe em branco para permitir todos os usuários do locatário.

## Object ID do grupo de administradores

Os membros deste grupo do Azure AD recebem acesso de administrador no ProxOrchestrator a cada login. Para achar o Object ID de um grupo:
1. No portal do Entra ID → **Groups**
2. Encontre o grupo e clique nele
3. Copie o "Object ID" da página de visão geral

## Validade do client secret

Os client secrets do Azure têm validade (no máximo 2 anos). Quando o segredo expira, o login pelo Entra ID para de funcionar. Crie um lembrete antes da data para gerar um novo segredo e atualizar o ProxOrchestrator.

## Problemas comuns

**"AADSTS70011: The provided request must include a 'redirect_uri' input"** — a redirect URI da página de configurações do Entra ID não foi registrada no Azure, ou está diferente (barra no final, http em vez de https). Copie a URI exata do ProxOrchestrator e cole no Azure.

**Os usuários entram, mas perdem o acesso depois de mudanças nos grupos do Azure** — a participação nos grupos do Entra ID é conferida no login. Os usuários precisam sair e entrar de novo para as mudanças valerem.

**"AADSTS50194: Application is not configured as a multi-tenant application"** — você registrou como single-tenant, mas usuários de outros locatários estão tentando entrar. Mude os tipos de conta aceitos no Azure ou ative o modo multi-tenant.

**Client secret expirado** — crie um novo client secret no Azure (Certificates & secrets → New client secret), copie o valor e atualize nas configurações do Entra ID do ProxOrchestrator. Não precisa mudar o ID do locatário nem o ID do cliente.
