# Nó

Detalhes do host Proxmox, como na seção *Node* da interface do Proxmox.
Só os administradores do ProxOrchestrator podem abrir esta página.

- **Serviços**: serviços do Proxmox e do sistema, com o estado de cada um.
  *dead* é normal para serviços que um nó único não usa (corosync) ou que
  outro serviço substitui (systemd-timesyncd quando o chrony está rodando).
- **Rede**: bridges, bonds, VLANs e placas de rede, com endereços e gateway.
- **DNS, hosts e hora**: servidores DNS, domínio de busca, `/etc/hosts`, fuso horário.
- **Discos**: discos físicos com a saúde S.M.A.R.T. e o desgaste dos SSDs
  (*Mostrar S.M.A.R.T.* para ver todos os atributos), grupos de volumes LVM,
  pools LVM-thin (uso de dados e de metadados), pools ZFS e montagens de pastas.
- **Repositórios e pacotes**: assinatura, repositórios do Proxmox ativados,
  fontes do APT e as versões instaladas dos pacotes principais.
- **Certificados**: os certificados do nó, com validade e impressão digital.
- **Dispositivos PCI**: dispositivos e grupos IOMMU (para passthrough de PCI).

## Somente leitura

Alterar o nó — reiniciar serviços, editar a rede ou o DNS, instalar
atualizações, reiniciar o host — exige `Sys.Modify` / `Sys.PowerMgmt`, e a
lista de atualizações disponíveis e o log do sistema exigem `Sys.Modify` /
`Sys.Syslog`. O token da API recomendado não tem nenhum deles, de propósito;
faça essas coisas na interface do Proxmox.
