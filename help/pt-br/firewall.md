# Firewall

O firewall do Proxmox tem vários níveis. Um pacote para um convidado só é
filtrado quando **todas** estas condições são verdadeiras:

1. o firewall do **datacenter** está ativado (Datacenter → Options);
2. o firewall do **convidado** está ativado (VM/CT → Firewall → Options);
3. a **placa de rede** do convidado tem a opção *Firewall* marcada.

## Níveis nesta página

- **Datacenter**: opções (ativar, política padrão de entrada/saída), regras que
  valem para o cluster inteiro, aliases e IPSets usáveis em qualquer lugar (`dc/nome`).
- **Nó**: regras para o próprio host Proxmox.
- **Grupos de segurança**: conjuntos de regras com nome, que um convidado
  insere com uma regra de direção *group*.

Alterar o datacenter, o nó e os grupos de segurança exige o privilégio
`Sys.Modify`. O token da API recomendado não tem, então esses níveis ficam só
para leitura aqui. O firewall do datacenter é ligado no Proxmox: confira as
regras antes, ou você pode se trancar fora da interface web e do SSH.

## Firewall do convidado (páginas de VM e contêiner)

Editável com o token recomendado (`VM.Config.Network`):

- **Opções**: ativar, política de entrada/saída, níveis de log, DHCP, NDP,
  router advertisement, filtros de MAC e de IP.
- **Regras**: direção, ação (ACCEPT, DROP, REJECT), uma *macro* (serviço
  predefinido como SSH, HTTP, DNS) **ou** protocolo e portas, origem e destino
  (IP, CIDR, faixa `a-b`, alias ou `+ipset`), interface (`net0`…), nível de log
  e comentário. Regras novas vão para o topo; vale a primeira regra que
  combinar. Use as setas para reordenar.
- **Aliases** e **IPSets** do convidado.

Com a política de entrada DROP, só chega ao convidado o que as regras
aceitarem. Adicione uma regra ACCEPT para o SSH ou a porta web **antes** de
ativar.

Se outra pessoa mudar as regras ao mesmo tempo, o Proxmox recusa a edição (a
lista mudou); recarregue a página e tente de novo.
