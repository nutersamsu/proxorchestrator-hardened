# Importar contêiner — enviar o pacote

Este é o primeiro passo para importar um contêiner de um pacote `.px`.

## Como enviar

1. Clique em **Escolher arquivo** e selecione um arquivo `.px` exportado de outra instância do ProxOrchestrator
2. Clique em **Enviar e continuar**

O arquivo é enviado e validado. Se o pacote for uma exportação de contêiner válida, você segue para a configuração, onde pode revisar e ajustar tudo antes de implantar.

## O que acontece depois

- **Passo 1 — Envio** (você está aqui): o pacote `.px` é enviado e validado
- **Passo 2 — Configuração**: revise as configurações do contêiner — nome, recursos, rede, armazenamento — e ajuste para o seu ambiente
- **Passo 3 — Implantação**: o ProxOrchestrator transfere o backup para o Proxmox e restaura o contêiner

## Requisitos

- O arquivo precisa ser um pacote `.px` gerado pela exportação de contêiner do ProxOrchestrator
- Pacotes de exportação de VM não são compatíveis — para eles, use a página de importação de VM
- O tamanho do arquivo é limitado pela configuração de envio do seu servidor

## Problemas comuns

**Erro "pacote inválido"** — o arquivo não é uma exportação de contêiner válida do ProxOrchestrator. Confira se ele foi exportado por uma instância do ProxOrchestrator (e não é um backup vzdump puro).

**Tempo esgotado no envio** — pacotes grandes podem passar do tempo limite padrão. Confira no servidor web (nginx) as opções `client_max_body_size` e `proxy_read_timeout`.
