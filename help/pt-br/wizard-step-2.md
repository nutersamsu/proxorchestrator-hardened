# Assistente de configuração — passo 2: chave SSH

O ProxOrchestrator usa autenticação por chave SSH em toda a comunicação com o seu servidor Proxmox. Este passo copia a chave pública do ProxOrchestrator para o Proxmox, para as próximas operações não precisarem de senha.

## Por que chave SSH?

- **Segurança** — a senha do root nunca é guardada. Ela é usada uma vez para copiar a chave e apagada da memória na hora.
- **Automação** — as transferências de disco (SFTP) e os comandos de criação de VM rodam em segundo plano, sem interação, pelas tarefas do Celery.
- **Rastreabilidade** — o `sshd` do Proxmox registra os logins por chave, então fica fácil ver quando o ProxOrchestrator se conectou.

## Como é a chave pública

O texto na caixa "Chave pública do ProxOrchestrator" é a chave pública da sua instância. Ela começa com `ssh-rsa` ou `ssh-ed25519`, segue com uma longa sequência em base64 e termina com um identificador. Pode compartilhar sem medo — não dá para descobrir a chave privada a partir dela.

## O que acontece ao clicar em "Copiar a chave e continuar"

O ProxOrchestrator:
1. Abre uma conexão SSH com o host Proxmox usando a senha do root que você digitou
2. Acrescenta a chave pública em `/root/.ssh/authorized_keys` no host Proxmox
3. Confere se a chave foi gravada certo, tentando entrar com ela
4. Apaga a senha do root da memória na hora — ela nunca é gravada em disco nem no banco de dados

## Instalar a chave você mesmo (alternativa)

Se o login do root por senha estiver desativado no Proxmox, ou se você preferir não digitar a senha aqui, abra **Login do root por senha desativado? Adicione a chave você mesmo**:

1. Na interface web do Proxmox, abra **o seu nó → Shell**
2. Clique em **Copiar comando** e cole a linha no Shell (ela acrescenta a chave em `/root/.ssh/authorized_keys`)
3. Volte aqui e clique em **Já adicionei — testar a chave**

## Problemas comuns

**"Authentication failed"** — a senha do root está errada. Digite de novo com cuidado. O root do Proxmox pode estar com a autenticação por senha desativada — confira `/etc/ssh/sshd_config` no Proxmox, ou use a instalação manual da chave acima.

**"Permission denied (publickey)"** — o SSH pode estar configurado para recusar senha. Use a instalação manual da chave acima (recomendado) ou ative temporariamente `PasswordAuthentication yes` em `/etc/ssh/sshd_config` e reinicie o sshd: `systemctl restart ssh`.

**"Host key verification failed"** — a impressão digital do host Proxmox mudou (pode acontecer se você reinstalou o Proxmox). Se tiver certeza de que o host é legítimo, apague a entrada dele no known_hosts do servidor do ProxOrchestrator.

**A chave já existe** — se você está rodando o assistente de novo, a chave pode já estar no authorized_keys. O ProxOrchestrator verifica duplicatas e não a adiciona duas vezes.
