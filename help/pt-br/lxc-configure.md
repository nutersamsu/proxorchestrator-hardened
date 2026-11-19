# Configurar contêiner LXC

Nesta página você configura o novo contêiner antes de criá-lo. Tudo pode ser mudado depois na interface web do Proxmox.

## Seções da configuração

### Geral
- **Nome do host** (obrigatório) — o nome do contêiner. Só letras, números e hífens.
- **CTID** — deixe em branco para usar o próximo ID livre, ou digite um número. O campo é validado na hora e avisa sobre conflitos.
- **Nó de destino** — em qual nó do cluster Proxmox criar o contêiner.
- **Descrição** — texto opcional.

### Recursos
- **Núcleos de CPU** — quantidade de núcleos (padrão: 1)
- **Memória (MB)** — RAM alocada (padrão: 512 MB)
- **Swap (MB)** — espaço de swap (padrão: 512 MB)

### Armazenamento
- **Armazenamento do disco raiz** — o pool do Proxmox para o rootfs do contêiner. Só aparecem pools que aceitam rootfs de contêiner.
- **Tamanho do disco raiz (GB)** — tamanho do sistema de arquivos raiz (padrão: 8 GB)

### Rede
- **Bridge** — a bridge de rede onde ligar o contêiner
- **Configuração de IP** — DHCP (automático) ou Estático (IP e gateway manuais)
- **Servidor DNS** — endereço do servidor de nomes (ex.: 8.8.8.8)
- **Domínio de busca** — domínio de busca do DNS

### Autenticação
- **Senha do root** — define uma senha para o usuário root. Deixe em branco para acesso só por chave.
- **Chave pública SSH** — cole uma chave pública SSH para entrar sem senha.

Defina pelo menos uma das duas, senha ou chave SSH; senão você não vai conseguir entrar no contêiner.

### Opções
- **Contêiner sem privilégios** — recomendado. Roda com privilégios de kernel reduzidos, mais seguro.
- **Ativar nesting** — necessário para rodar Docker ou outros contêineres dentro deste LXC.
- **Iniciar com o host** — liga automaticamente quando o host Proxmox liga.
- **Iniciar depois de criar** — liga o contêiner logo depois de criado.

## Criar o contêiner

O cartão de resumo à direita mostra o template e o armazenamento escolhidos. Clique em **Criar contêiner** para começar. Você vai para a página de andamento.
