# Importar VM — enviar a imagem de disco

Este é o primeiro passo para importar uma VM no Proxmox. Você envia o arquivo da imagem de disco, que o ProxOrchestrator converte (se precisar) e prepara para a configuração da VM.

## Formatos aceitos

| Formato | Extensão | Observações |
|---------|----------|-------------|
| QCOW2   | `.qcow2` | Formato nativo do Proxmox — não precisa converter, é o caminho mais rápido |
| VMDK    | `.vmdk`  | Formato do VMware — convertido automaticamente para qcow2 |
| VHD     | `.vhd`   | Formato VPC do Hyper-V — convertido automaticamente |
| VHDX    | `.vhdx`  | Formato moderno do Hyper-V — convertido automaticamente |
| RAW     | `.raw`, `.img` | Imagem de disco raw — convertida para qcow2 |
| OVA     | `.ova`   | Open Virtualization Archive — discos extraídos e convertidos |

Todos os formatos que não são qcow2 são convertidos com `qemu-img convert -O qcow2` antes de ir para o Proxmox.

## Como enviar

**Jeito 1 — arrastar e soltar:** arraste o arquivo da imagem do seu gerenciador de arquivos até a área tracejada. A borda fica azul quando o arquivo está no lugar certo.

**Jeito 2 — procurar:** clique em qualquer lugar da área para abrir o seletor de arquivos e escolha a imagem de disco.

Depois de escolher, aparecem o nome e o tamanho do arquivo e o botão "Enviar e continuar". Clique nele para começar o envio.

## Arquivos grandes

Para imagens de disco grandes (10 GB ou mais):
- Mantenha a aba do navegador aberta durante o envio
- A barra de progresso mostra o andamento em tempo real
- A velocidade depende da sua conexão com o servidor do ProxOrchestrator
- O ProxOrchestrator não limita o tamanho do arquivo (o limite é o espaço em disco do servidor)
- Se você fechar o navegador, o envio é interrompido

## Arquivos OVA

Arquivos OVA são pacotes com os discos da VM (VMDK), um manifesto e um descritor OVF. O ProxOrchestrator:
1. Extrai o pacote OVA
2. Lê o descritor OVF e preenche a configuração de hardware (CPU, memória, firmware, discos)
3. Converte cada disco VMDK para qcow2
4. Importa **todos** os discos do OVA — você confere tudo na tela de configuração

Alguns OVAs de appliances trazem também uma ISO de instalação; nesse caso a tela de configuração pede um armazenamento do Proxmox para enviá-la.

## Problemas comuns

**"Formato de arquivo não suportado"** — só as extensões da lista são aceitas. Se o arquivo usa outra extensão mas é de um desses formatos, renomeie. Por exemplo, um `.img` que é uma imagem raw pode ser renomeado para `.raw`.

**O envio parece parado em 0%** — pode acontecer com arquivos muito grandes enquanto eles são carregados. Espere alguns segundos — se não sair do lugar, confira a sua conexão de rede.

**O envio falha no meio** — normalmente é uma queda de rede. Escolha o arquivo de novo e envie outra vez. O envio parcial que falhou é apagado automaticamente.

**"Não há espaço em disco suficiente"** — a pasta temporária do servidor do ProxOrchestrator (configurada no passo 5 do assistente) não tem espaço. Libere espaço ou aponte a pasta temporária para um disco maior.
