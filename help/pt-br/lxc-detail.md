# Detalhes do contêiner

Esta página mostra a configuração completa de um contêiner LXC, lida ao vivo pela API do Proxmox. Pelo cabeçalho da página você também controla a energia do contêiner.

## Ações de energia

Os botões no canto superior direito dependem do estado atual do contêiner:

- **Desligar** (contêineres rodando) — desligamento normal pelo sistema de inicialização do contêiner. O sistema convidado salva os dados e desliga direito.
- **Forçar parada** (contêineres rodando) — mata o contêiner na hora. Use só quando ele travou e não responde ao desligamento normal. Há risco de perder dados.
- **Reiniciar** (contêineres rodando) — reinício normal.
- **Iniciar** (contêineres parados) — liga o contêiner.
- **Console** (contêineres rodando) — abre uma sessão de terminal noVNC interativa em outra aba.
- **Exportar contêiner** — empacota o contêiner num arquivo `.px` portátil, para migrar ou guardar.

Depois de clicar numa ação, a faixa de estado se atualiza. O contêiner pode levar alguns segundos para mudar de estado.

## Faixa de estado

A faixa colorida no topo mostra o estado atual do contêiner e se atualiza a cada 5 segundos:
- **Verde** — rodando, com o uso de CPU e RAM ao vivo
- **Vermelho** — parado

Os contêineres rodando mostram o uso de CPU em porcentagem, o uso de memória e o tempo ligado em tempo real.

## Seções da configuração

### Geral
Propriedades básicas do contêiner: CTID, nome, tipo de sistema, arquitetura e descrição. Use o lápis da descrição para editar as notas (Markdown, como no Proxmox).

### Opções
Opções e flags do contêiner: modo de privilégio (sem privilégios é o recomendado por segurança), iniciar com o host, ordem de inicialização, proteção, recursos ativados (ex.: nesting para Docker dentro do LXC), modo de console e quantidade de TTYs, caminho do hookscript, estado de bloqueio e tags. Só os valores que você muda são enviados ao Proxmox.

- A **ordem de inicialização** exige o privilégio `Sys.Modify`; com o token da API recomendado ela fica só para leitura.
- O **hookscript** só pode ser alterado pelo `root@pam` (regra do Proxmox), então aqui ele fica sempre só para leitura.

### CPU
Mostra a quantidade de núcleos, o limite de CPU (0 = ilimitado) e as unidades de CPU (peso no agendamento em relação aos outros contêineres, padrão 1024).

### Memória
Mostra a RAM e o swap configurados, em MB.

### DNS
Nome do host, servidores DNS, domínio de busca e fuso horário. "Configuração do host" significa que o contêiner herda esses valores do host Proxmox em vez de ter configuração própria. Clique no lápis para mudar o nome do host, os servidores DNS e o domínio de busca; o Proxmox aplica na hora, mesmo com o contêiner rodando.

### Armazenamento
Uma tabela com todos os pontos de montagem do contêiner:
- **Montagem** — `rootfs`, `mp0`, `mp1` etc.
- **Armazenamento** — em qual pool do Proxmox o volume está
- **Tamanho** — tamanho do volume

**Mover** copia um volume para outro armazenamento que aceite volumes de contêiner (`rootdir`). O disco raiz só pode ser movido com o contêiner parado; o andamento abre no log da tarefa.

### Interfaces de rede
Mostra todas as placas de rede com a configuração completa:
- **Interface** — `net0`, `net1` etc.
- **Nome** — o nome da interface dentro do contêiner (ex.: `eth0`)
- **Tipo** — tipo de dispositivo de rede (ex.: `veth`)
- **Bridge** — em qual bridge do Proxmox a placa está ligada
- **Endereço MAC** — endereço de hardware
- **Configuração de IP** — endereço IP com sub-rede e gateway
- **VLAN** — tag de VLAN, se houver
- **Firewall** — se o firewall do Proxmox está ativado nesta placa
- **Limite de banda** — limite em MB/s, se houver

## Snapshots

Snapshots guardam o estado completo de um contêiner — configuração e conteúdo do disco — num momento. São úteis antes de mudanças arriscadas (atualização do sistema, edição de configuração, instalação de programas), para voltar rápido se algo der errado.

### Criar um snapshot
Digite um nome (letras, números, hífens e sublinhados) e uma descrição opcional, e clique em **Tirar snapshot**. Dá para tirar snapshots com o contêiner rodando ou parado — sem parada.

### Voltar a um snapshot
Clique em **Voltar** para retornar o contêiner exatamente ao estado do momento do snapshot. **Isso é destrutivo** — todas as mudanças feitas depois do snapshot (arquivos, configuração, dados) serão perdidas. Se o contêiner estiver rodando, o Proxmox o para antes de voltar.

### Excluir um snapshot
Clique no botão de excluir para remover um snapshot. Isso libera o espaço em disco usado pelas diferenças do snapshot. Excluir um snapshot **não** muda o estado atual do contêiner.

### Dicas
- Tire um snapshot antes de atualizar pacotes ou mudar a configuração
- Dê nomes descritivos aos snapshots (ex.: `antes-de-atualizar-nginx`)
- Não guarde snapshots demais — cada um ocupa espaço extra e pode deixar a E/S mais lenta em alguns armazenamentos

## Templates

**Converter em template** (contêineres parados) transforma o contêiner num template. Templates não podem ser iniciados; crie contêineres novos a partir deles com **Clonar**. Não dá para desfazer por aqui.

## Desempenho

Os gráficos de CPU, memória, rede e disco (de uma hora a um ano, média ou máximo) ficam no fim da página.
