# Scripts da comunidade

Os scripts da comunidade permitem implantar aplicativos auto-hospedados populares como contêineres LXC no seu nó Proxmox com um clique. Eles vêm do projeto [community-scripts/ProxmoxVE](https://github.com/community-scripts/ProxmoxVE) (antigos scripts do Tteck) — uma biblioteca com mais de 680 scripts de implantação em que a comunidade Proxmox confia.

## Como funciona

1. **Procurar** — busque ou filtre por categoria para achar o app que quer.
2. **Configurar** — escolha o nó de destino, o armazenamento e, se quiser, mude os recursos padrão (CPU, RAM, disco).
3. **Implantar** — o ProxOrchestrator entra por SSH no seu host Proxmox e roda o script sem interação. O script faz tudo: baixa o template do sistema, cria o contêiner, instala o aplicativo e o liga.

## Procurando apps

- **Barra de busca** — digite para filtrar por nome, tags ou descrição. Os resultados mudam enquanto você digita (com 300 ms de espera).
- **Categorias na lateral** — clique numa categoria para filtrar (ex.: servidores de mídia, automação residencial, bancos de dados). Clique em "Todos os scripts" para limpar o filtro.
- **Cartões dos apps** — cada cartão mostra o nome, o logo, uma descrição curta e os recursos padrão. Clique num cartão para abrir os detalhes, com a descrição completa, as especificações e o botão **Implantar**.

## Implantando um app

A página de implantação mostra:

- **Coluna esquerda** — cartão com as informações do app e as especificações padrão (CPU, RAM, disco, sistema).
- **Coluna direita** — formulário de configuração:
  - **Nó do Proxmox** — em qual nó implantar.
  - **Armazenamento do contêiner** — onde guardar o disco do contêiner. Deixe "Automático" para o script escolher o padrão dele.
  - **Armazenamento de templates** — onde baixar o template do sistema. Escolher aqui evita uma pergunta interativa quando vários armazenamentos guardam templates.
  - **Nome, CPU, RAM, disco** — vêm com os valores recomendados pelo script. Mude se precisar.
  - **Rede** — escolha da bridge e configuração de IP (DHCP ou fixo).

Clique em **Implantar** para começar. Você vai para a página de andamento.

## Andamento e cancelamento

A página de andamento mostra as etapas ao vivo, em duas fases:

1. **Baixando o script** — busca o script no GitHub.
2. **Rodando o script** — executa no seu host Proxmox, com o terminal ao vivo na tela.

A página se atualiza sozinha a cada 3 segundos. Você pode cancelar uma implantação em andamento quando quiser.

## Depois da implantação

Quando o script termina:

- **Sucesso** — aparece o CTID atribuído e links para ver o contêiner no inventário.
- **Falha** — aparece a saída de erro. Você pode tentar de novo com a mesma configuração.

O novo contêiner aparece no inventário de contêineres na hora.

## Como os scripts rodam

Os scripts da comunidade rodam direto no seu host Proxmox (do mesmo jeito que quando você os roda à mão). O ProxOrchestrator passa variáveis de ambiente `var_*` para o script rodar sem interação — ele pula as perguntas e usa os valores que você configurou.

Nada sai da sua rede, a não ser a requisição HTTPS ao GitHub para baixar o próprio script.

## Segurança

- **As URLs dos scripts são validadas** contra o catálogo incluído. Não dá para implantar scripts quaisquer.
- **Todos os valores digitados são escapados** para o shell, para evitar injeção de comandos.
- **Os scripts rodam como root** no host Proxmox — isso é necessário para criar contêineres (`pct create`). É o mesmo nível de privilégio de quando você roda os scripts à mão.
- **Tempo limite** — scripts demorados podem ser cancelados pela página de andamento.

## Atualizar o catálogo

O catálogo de scripts vem junto com o ProxOrchestrator e também é atualizado a cada `update.sh`. Quando saem scripts novos no projeto original, aparece um aviso **Atualização disponível** na barra de busca. Clique nele para refazer o catálogo direto do GitHub — não precisa atualizar o ProxOrchestrator. A atualização roda em segundo plano e a página recarrega ao terminar.

## Problemas comuns

**"Não foi possível carregar os recursos do Proxmox"** — a API do Proxmox pode estar inacessível. Confira as configurações de conexão.

**O script falha com "permission denied"** — confira se a chave SSH configurada no ProxOrchestrator tem acesso de root ao host Proxmox.

**O contêiner foi criado, mas o app não funciona** — alguns scripts mostram instruções de configuração (senhas padrão, endereço da interface web) no final da saída. Veja o terminal da implantação ou o console do contêiner no Proxmox.

**O script falha com "TERM environment variable not set"** — isso foi corrigido numa atualização recente. Se aparecer, confira se você está usando a versão mais nova do ProxOrchestrator.
