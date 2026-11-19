# Importar contêiner — configuração

Nesta página você revisa e ajusta as configurações do contêiner antes de implantá-lo no nó Proxmox. O formulário vem preenchido com os valores do pacote exportado.

## Seções da configuração

### Geral
- **Nome do host** (obrigatório) — o nome do contêiner. Vem da exportação; mude para evitar conflito se já existir um contêiner com o mesmo nome.
- **CTID** — deixe em branco para usar o próximo ID livre, ou digite um número. O campo é validado na hora e avisa sobre conflitos.
- **Nó de destino** — em qual nó do cluster Proxmox criar o contêiner.
- **Descrição** — texto opcional.

### Recursos
- **Núcleos de CPU** — quantidade de núcleos do contêiner
- **Memória (MB)** — RAM alocada
- **Swap (MB)** — espaço de swap

Vêm da configuração do contêiner de origem. Ajuste conforme a capacidade do servidor de destino.

### Armazenamento
- **Pool de armazenamento** — o pool do Proxmox para o rootfs do contêiner. Só aparecem pools que aceitam contêineres, com o espaço livre de cada um.

### Rede
- **Bridge** — a bridge de rede onde ligar o contêiner. Vem da exportação; mude se o destino usa outra bridge.
- **Configuração de IP** — DHCP ou Estático. Se a origem usava IP fixo, provavelmente você vai precisar mudar para evitar conflito.
- **Servidor DNS** e **Domínio de busca** — vêm da exportação.

### Opções
- **Contêiner sem privilégios** — recomendado por segurança. Roda com privilégios de kernel reduzidos.
- **Ativar nesting** — necessário para rodar Docker ou outros contêineres dentro deste LXC.
- **Iniciar com o host** — liga este contêiner automaticamente quando o host Proxmox liga.
- **Iniciar o contêiner depois de importar** — liga o contêiner logo depois de criado.

## Implantar

Clique em **Implantar contêiner** para começar a importação. Você vai para a página de andamento, onde acompanha cada etapa em tempo real.

## Dicas

- Confira sempre se a bridge de rede existe no nó de destino
- Se for importar para outra sub-rede, ajuste a configuração de IP
- Confira se o pool escolhido tem espaço livre suficiente para o rootfs do contêiner
