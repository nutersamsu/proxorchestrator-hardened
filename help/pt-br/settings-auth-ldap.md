# Configurações de autenticação — LDAP / Active Directory

O ProxOrchestrator aceita autenticação LDAP, para a sua equipe entrar com as credenciais do diretório que já usa (Active Directory, OpenLDAP, FreeIPA etc.).

## Como funciona a autenticação LDAP

1. O usuário digita o usuário e a senha do AD/LDAP na página de login do ProxOrchestrator
2. O ProxOrchestrator se conecta ao servidor LDAP e procura o registro do usuário
3. O ProxOrchestrator tenta fazer bind (autenticar) como o usuário, com a senha dele
4. Se der certo, o usuário entra no ProxOrchestrator
5. Se houver restrição por grupo, o ProxOrchestrator confere a participação no grupo antes de liberar o acesso

## URI do servidor LDAP

A URI precisa seguir o formato `ldap://servidor:porta` ou `ldaps://servidor:porta`

- `ldap://dc.example.com:389` — sem criptografia ou com STARTTLS
- `ldaps://dc.example.com:636` — SSL/TLS (LDAPS)

No Active Directory, use o nome ou o IP do controlador de domínio. Em ambientes com vários controladores, use um endereço LDAP com balanceamento ou o nome do domínio do AD (ex.: `ldap://example.com`).

## DN e senha de bind

O DN de bind é o Distinguished Name de uma conta de serviço que o ProxOrchestrator usa para fazer buscas no diretório. Essa conta precisa de leitura nos objetos de usuário e grupo.

Exemplo de DN de bind no Active Directory:
`CN=proxorchestrator-svc,OU=Service Accounts,DC=example,DC=com`

Exemplo de DN de bind no OpenLDAP:
`uid=proxorchestrator,ou=service,dc=example,dc=com`

Use uma conta de serviço só para isso, com o mínimo de permissões — leitura de usuários e grupos basta.

## Base e filtro de busca de usuários

**Base de busca de usuários** — o Distinguished Name do contêiner onde procurar os usuários. Para procurar no diretório inteiro: `DC=example,DC=com`. Para limitar a uma OU: `OU=Staff,DC=example,DC=com`.

**Filtro de busca de usuários** — filtro LDAP para achar um usuário pelo nome de login. No Active Directory, o filtro padrão é:
`(sAMAccountName=%(user)s)`

No OpenLDAP, normalmente:
`(uid=%(user)s)`

`%(user)s` é trocado pelo nome de usuário digitado no login.

## Restrições por grupo

**Grupo obrigatório** — só os membros deste grupo LDAP podem entrar. Se ficar em branco, todos os usuários encontrados na base de busca podem entrar. Digite o Distinguished Name completo do grupo.

Exemplo: `CN=ProxOrchestratorUsers,OU=Groups,DC=example,DC=com`

**Grupo de administradores** — os membros deste grupo recebem automaticamente acesso de administrador no ProxOrchestrator. Se você torna alguém administrador adicionando a pessoa a esse grupo no AD, o acesso dela no ProxOrchestrator muda no próximo login.

## Opções de TLS

**STARTTLS** — transforma uma conexão LDAP sem criptografia numa conexão criptografada. Use com URI `ldap://` na porta 389 quando o seu AD aceitar STARTTLS (a maioria dos AD modernos aceita). É preferível ao LDAPS em portas sem SSL.

**Ignorar verificação do certificado** — desativa a validação do certificado TLS. **Use só para testes.** Em produção, garanta que o certificado do servidor LDAP seja confiável para o ProxOrchestrator (cole a CA no campo *Certificado de CA confiável* ou use as CAs do sistema).

## Testar a conexão

Clique em "Testar conexão" depois de preencher (sem salvar). O teste tenta fazer bind no servidor LDAP com as credenciais da conta de serviço e faz uma busca de teste. O resultado mostra se o bind deu certo e quantos usuários existem no escopo da busca.

## Problemas comuns

**"No such object"** — o DN da base de busca não existe. Confira se há erro de digitação na estrutura de OU/DC.

**"Invalid credentials"** — o DN ou a senha de bind estão errados. Confira as credenciais da conta de serviço no AD.

**"Can't contact LDAP server"** — problema de rede. Confira se o servidor LDAP é alcançável na porta informada a partir do servidor do ProxOrchestrator.

**Os usuários entram, mas não viram administradores** — confira se o DN do grupo de administradores está exato (maiúsculas e minúsculas não importam, mas a estrutura precisa estar certa). Use um navegador LDAP para confirmar o DN do grupo.

**"Certificate verify failed"** — o certificado do servidor LDAP não é confiável. Cole a CA no campo *Certificado de CA confiável*, use LDAP (sem SSL) com STARTTLS, ou ative "Ignorar verificação do certificado" só temporariamente para testar.
