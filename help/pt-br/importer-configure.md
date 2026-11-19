# Importar VM — configurar a VM

Nesta tela você define todas as configurações da nova VM que será criada no Proxmox. A imagem de disco enviada aparece à direita — o resto define como a VM será criada.

## Geral

**Nome da VM** — o nome que o Proxmox vai mostrar para esta VM. Use só letras, números e hífens, sem espaços nem caracteres especiais. Ele vira o nome da VM no Proxmox.

**VMID** — o número da VM no Proxmox. O ProxOrchestrator preenche com o próximo ID livre da sua faixa de VMIDs. Uma verificação ao vivo valida o VMID enquanto você digita — verde é livre, vermelho já está em uso.

**Nó de destino** — em qual nó do cluster Proxmox a VM vai ficar. O padrão é o nó padrão configurado.

**Tipo de sistema** — informa ao Proxmox qual sistema operacional a VM vai rodar. Isso muda alguns padrões e a exibição no Proxmox. Escolhas comuns: `win11`, `win10`, `l26` (kernel Linux 2.6 ou mais novo).

**Iniciar com o host** — se marcado, a VM liga sozinha quando o nó Proxmox liga.

## Firmware e boot

**Tipo de BIOS** — duas opções:
- **SeaBIOS** — BIOS tradicional. Use em imagens de sistemas mais antigos, ou quando não souber o que a VM de origem usava.
- **OVMF (UEFI)** — use se a VM de origem dava boot em UEFI. Obrigatório para Windows 11, Secure Boot e algumas distribuições Linux modernas.

Com OVMF escolhido, aparecem mais opções:
- **Armazenamento do disco EFI** — onde fica o disco de variáveis EFI. Use o mesmo pool do disco da VM.
- **Secure Boot** — obrigatório para Windows 11. Exige OVMF.
- **TPM 2.0** — Trusted Platform Module virtual. Obrigatório para Windows 11 e alguns softwares corporativos. Exige OVMF.

**Como saber se a VM de origem era UEFI:** no hipervisor de origem (VMware/Hyper-V), veja o tipo de firmware nas configurações da VM. Se a VM tinha Secure Boot ou TPM, com certeza é UEFI.

## CPU

**Tipo de CPU** — como a CPU virtual aparece para o sistema convidado:
- `host` — mostra o modelo real da CPU do host. Melhor desempenho, mas a VM não pode ser migrada ao vivo para nós com CPUs diferentes.
- `x86-64-v2-AES` — compatibilidade ampla. Recomendado para a maioria das importações, principalmente se você pode migrar VMs entre nós.
- `kvm64` — base antiga. Máxima compatibilidade, mínimo desempenho.

**Sockets × núcleos = total de vCPUs.** Para a maioria dos usos, recomenda-se 1 socket com vários núcleos.

## Memória

**RAM** — memória da VM, em GB.

**Balloon** — gerenciamento dinâmico de memória. Quando ativado, o Proxmox pode recuperar a memória que a VM não está usando. O "mínimo do balloon" é a RAM que nunca é recuperada. Desative se o sistema convidado não tiver o driver de balloon (comum em importações de Windows sem os drivers VirtIO).

## Disco

**Pool de armazenamento** — onde a imagem qcow2 importada fica depois da transferência.

**Barramento do disco** — como o disco aparece para o sistema convidado:
- VirtIO SCSI — melhor desempenho. Exige drivers VirtIO no convidado.
- IDE — legado. Máxima compatibilidade. Use se a VM não der boot com SCSI.
- SATA — boa compatibilidade, desempenho médio.

**Descarte (TRIM)** — repassa os comandos de descarte (TRIM) do convidado para o armazenamento. Recomendado se o armazenamento for em SSD. Exige que o sistema convidado aceite TRIM.

## Rede

**Bridge** — em qual bridge Linux ligar a placa de rede da VM. A `vmbr0` liga à sua rede física.

**Modelo de rede** — como a placa de rede aparece para o convidado:
- `virtio` — melhor desempenho. Exige drivers VirtIO.
- `e1000` — emulação Intel. Funciona sem drivers especiais na maioria dos sistemas.
- `rtl8139` — emulação antiga. Máxima compatibilidade.

**Tag de VLAN** — marcação de VLAN opcional. Deixe em branco se não usa VLANs.

## Casos comuns de importação

**VM Windows vinda do VMware (VMDK):** OVMF UEFI, Secure Boot desligado (a não ser que a origem usasse), TPM desligado (a não ser Windows 11), rede e1000 (o VirtIO pode ser adicionado depois, instalando os drivers).

**VM Linux vinda do VMware:** SeaBIOS costuma funcionar. VirtIO SCSI + rede VirtIO para o melhor desempenho, se a distribuição aceitar (a maioria aceita).

**Windows 11:** exige OVMF UEFI + Secure Boot + TPM 2.0. Sem exceção.

**Origem desconhecida:** comece com SeaBIOS, disco IDE e rede e1000 para máxima compatibilidade. Você sempre pode reconfigurar no Proxmox depois que a VM der boot.

**Appliances (Cisco, Aruba etc.):** use uma **predefinição de hardware** no topo da página, que já escolhe configurações compatíveis com KVM.
