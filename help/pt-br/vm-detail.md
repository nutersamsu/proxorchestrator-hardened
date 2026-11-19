# Detalhes da VM

Esta página mostra a configuração completa de uma VM do Proxmox, lida ao vivo pela API do Proxmox. Pelo cabeçalho da página você também controla a energia da VM.

## Ações de energia

Os botões no canto superior direito dependem do estado atual da VM:

- **Desligar** (VMs rodando) — desligamento normal por ACPI. O sistema convidado salva os dados e desliga direito. Pode levar de 30 a 60 segundos.
- **Forçar parada** (VMs rodando) — corte de energia imediato. Use só quando a VM travou e não responde ao desligamento normal. Há risco de perder dados.
- **Reiniciar** (VMs rodando) — reinício normal pelo sinal ACPI.
- **Mais** (VMs rodando):
  - **Reset** — reinício forçado, como apertar o botão de reset. Sem desligamento limpo.
  - **Pausar** — congela a VM na RAM. **Retomar** continua de onde parou.
  - **Hibernar** — salva a RAM em disco e para a VM. **Iniciar** volta exatamente de onde estava.
- **Iniciar** (VMs paradas) — liga a VM (ou retoma uma hibernada).
- **Retomar** (VMs pausadas) — continua uma VM pausada.
- **Converter em template** (VMs paradas) — transforma a VM num template. Templates não podem ser iniciados; crie VMs novas a partir deles com **Clonar** (um clone vinculado é instantâneo e compartilha os discos do template). Não dá para desfazer por aqui.

Depois de clicar numa ação, a faixa de estado se atualiza. A VM pode levar alguns segundos para mudar de estado — recarregue a página se o estado não mudar.

## Faixa de estado

A faixa colorida no topo mostra o estado atual da VM:
- **Verde** — rodando, com o uso de CPU e RAM ao vivo
- **Vermelho** — parada
- **Amarelo** — pausada/suspensa

As VMs rodando mostram o uso de CPU em porcentagem e o uso de memória em tempo real, junto com o tempo ligado.

## Seções da configuração

### Geral
Propriedades básicas da VM: VMID, nome, tipo de sistema e descrição. Use **Renomear VM** para mudar o nome e o lápis da descrição para editar as notas (Markdown, como no Proxmox).

### Firmware e boot
Mostra o tipo de BIOS (SeaBIOS ou OVMF), se há disco EFI e TPM configurados, a ordem de boot e se a VM inicia com o host.

**Tipo de BIOS errado** — se uma VM não der boot depois da importação, confira se o tipo de BIOS aqui é o mesmo que a VM original usava. Uma VM UEFI configurada com SeaBIOS não dá boot direito.

### CPU
Mostra o tipo de CPU, sockets, núcleos e o total de vCPUs. Uma VM com 2 sockets × 4 núcleos tem 8 vCPUs no total.

**Dica de desempenho:** menos sockets com mais núcleos costuma ser mais eficiente que muitos sockets com poucos núcleos. O sistema convidado vê o mesmo total de vCPUs nos dois casos.

### Memória
Mostra a RAM configurada e as opções de balloon. O balloon deixa o Proxmox recuperar dinamicamente a memória sem uso das VMs quando falta memória no host.

### Discos
Uma tabela com todos os discos anexados à VM:
- **Interface** — `scsi0`, `ide0`, `sata0`, `virtio0` etc.
- **Armazenamento** — em qual pool do Proxmox o disco está
- **Tamanho** — tamanho do disco
- **Formato** — `qcow2`, `raw` etc.

Se você importou a VM pelo ProxOrchestrator, o disco principal deve ser `scsi0` (ou `ide0`, se escolheu IDE na configuração), no formato `qcow2`.

**Mover** copia um disco para outro armazenamento (podendo converter para qcow2/raw) e pode apagar a origem depois. Funciona com a VM rodando; o andamento abre no log da tarefa.

### Interfaces de rede
Mostra todas as placas de rede, com modelo, bridge, endereço MAC e tag de VLAN. Se uma VM está sem rede, confira se a bridge mostrada aqui corresponde à sua rede física no Proxmox.

### Opções
A aba *Options* do Proxmox: tipo de sistema, QEMU guest agent, proteção, hotplug, ponteiro tablet, ACPI, KVM, RTC em hora local, congelar a CPU na inicialização, tags, vídeo (tipo de VGA e memória) e o controlador SCSI. Só os valores que você muda são enviados ao Proxmox.

A **ordem de início/desligamento** exige o privilégio `Sys.Modify`. Com o token da API recomendado, ela aparece só para leitura.

### Vídeo e outros hardwares
Tipo de vídeo, controlador SCSI, tipo de máquina e dispositivos que o app não edita (passthrough de USB/PCI, portas seriais, áudio, RNG…). Adicionar dispositivos de passthrough exige root ou mapeamentos de recursos no Proxmox.

### Guest agent
Aparece nas VMs rodando com o agente ativado: sistema operacional, nome do host, todos os endereços IP e o uso dos sistemas de arquivos, lidos pelo QEMU guest agent dentro da VM.

### Cloud-Init
Usuário, senha, chaves SSH, DNS e a configuração de IP de cada interface de rede. Sem drive de cloud-init, o cartão oferece adicionar um. Os valores só chegam ao convidado depois de **Regenerar imagem** e de um boot; o cartão lista os valores que ainda não estão na imagem.

### Desempenho
Gráficos de CPU, memória, rede e disco (de uma hora a um ano, média ou máximo).

## Console

**Console** (VMs rodando) abre o console noVNC em outra aba.
