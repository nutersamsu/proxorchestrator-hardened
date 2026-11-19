# Painel

O painel dá uma visão rápida do seu ambiente Proxmox e da atividade recente.

## O que aparece aqui

- **Contagem de VMs** — VMs rodando, paradas e pausadas no nó Proxmox conectado
- **Ações rápidas** — atalhos para importar uma VM ou ver o inventário
- **Importações recentes** — os 5 últimos jobs de importação, com estado e links
- **Informações do sistema** — host Proxmox atual, estado da conexão com a API e da chave SSH

## Primeiros passos

Se é a primeira vez, clique em **Abrir assistente de configuração** para conectar o ProxOrchestrator ao seu servidor Proxmox. O assistente guia você em:

1. Informar os dados do host Proxmox
2. Copiar uma chave SSH para o servidor Proxmox
3. Criar e verificar um token da API
4. Descobrir o ambiente (nós, armazenamentos, redes)
5. Definir padrões sensatos

## Resumo do nó

O cartão no topo mostra os mesmos dados do painel **Summary** do nó na interface web do Proxmox (sem os gráficos): uso de CPU, memória, disco raiz e swap, espera de E/S, carga média, compartilhamento KSM, modo de boot, modelo da CPU, versão do kernel e do `pve-manager`, e tempo ligado. Ele se atualiza a cada 30 segundos.

As **temperaturas** não vêm pela API do Proxmox, então são lidas pela conexão SSH do app direto de `/sys/class/hwmon` — não é preciso instalar nada no host. Aparece uma leitura por dispositivo (pacote da CPU, "Composite" do NVMe etc.); passe o mouse sobre um item para ver os outros sensores do mesmo dispositivo (por exemplo, cada núcleo da CPU). Os valores ficam amarelos e vermelhos ao se aproximar do limite crítico do sensor (ou de 70/85 °C quando o sensor não informa limite).

- *"precisa de Sys.Audit"* — o token da API não consegue ler o estado do nó; dê a ele a função **PVEAuditor** em `/`.
- *"SSH indisponível"* — a chave SSH não está funcionando; confira em **Configurações → Proxmox**.
- *"O host não expõe sensores"* — comum em hosts Proxmox virtuais/aninhados.

## Contagem de VMs

A contagem de VMs vem ao vivo da API do Proxmox toda vez que o painel é aberto. Se a contagem ficar carregando e nunca terminar, confira o estado do token da API em **Configurações → Proxmox**.

## Importações recentes

A tabela mostra os seus 5 últimos jobs de importação. Clique na seta ao lado de um job concluído para ir à página da VM. Jobs em andamento mostram um indicador; clique nele para ir à tela de andamento.

## Problemas comuns

**O assistente de configuração continua aparecendo** — a configuração não foi concluída. Rode o assistente do começo ao fim para configurar a conexão com o Proxmox.

**A contagem de VMs mostra 0** — confira se o token da API ainda é válido. Tokens do Proxmox podem ser revogados na interface web, em Datacenter → Permissions → API Tokens.

**O estado da API mostra Desconectado** — confira se o host Proxmox é alcançável na porta 8006 a partir deste servidor. Verifique as regras de firewall se precisar.

**A chave SSH aparece como "Não configurada"** — rode o assistente de novo (passo 2) para copiar a chave SSH, ou adicione a chave manualmente no authorized_keys do root no host Proxmox.
