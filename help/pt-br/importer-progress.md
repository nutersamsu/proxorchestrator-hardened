# Importar VM — andamento da implantação

Esta tela mostra em tempo real o andamento da importação da sua VM. As etapas rodam como uma tarefa em segundo plano e a tela se atualiza sozinha a cada 2 segundos.

## Etapas da importação

### 1. Validar o envio
Confere se o arquivo enviado existe, pode ser lido e se o formato detectado combina com a extensão. Falha logo se o arquivo foi corrompido no envio.

### 2. Detectar o formato
Roda `qemu-img info` no arquivo para confirmar o formato real do disco. É a informação que vale — a extensão pode mentir. O formato detectado define se é preciso converter.

### 3. Converter para QCOW2 *(pulado em arquivos qcow2)*
Roda `qemu-img convert -O qcow2 -p` no disco de origem. Discos grandes podem levar bastante tempo aqui:
- Um VMDK de 50 GB pode levar de 5 a 15 minutos, dependendo da compressão
- Uma imagem raw converte rápido, porque não há descompressão
- A porcentagem aparece durante a conversão

### 4. Validar o VMID
Confere pela API do Proxmox se o VMID pedido continua livre. O assistente sugeriu um VMID na configuração — aqui ele confirma que ainda está livre na hora de implantar.

### 5. Criar a VM
Chama a API do Proxmox (`POST /nodes/{node}/qemu`) para criar a configuração da VM sem disco. Isso cria a VM com todas as configurações: CPU, RAM, rede, firmware etc.

### 6. Transferir o disco por SFTP
Transfere o arquivo qcow2 convertido para o nó Proxmox por SFTP. O andamento aparece em porcentagem. A velocidade depende da conexão entre o servidor do ProxOrchestrator e o Proxmox. Discos grandes (50 GB ou mais) podem levar de 10 a 30 minutos ou mais numa rede gigabit.

### 7. Importar o disco na VM
Roda `qm importdisk {vmid} {arquivo} {armazenamento}` no nó Proxmox via SSH. Isso faz o Proxmox registrar o arquivo de disco como pertencente a esta VM no pool escolhido. Normalmente termina em segundos.

### 8. Anexar o disco
Roda `qm set {vmid} --scsi0 {armazenamento}:{vmid}/vm-{vmid}-disk-0.qcow2` (ou o equivalente para a interface de disco configurada) para anexar o disco importado à VM. Isso liga o disco na configuração da VM.

### 9. Finalizar
Apaga os arquivos temporários no servidor do ProxOrchestrator e no Proxmox, marca o job de importação como concluído no banco de dados e atualiza o controle da faixa de VMIDs.

## O que fazer enquanto espera

- Não precisa deixar esta aba aberta — a importação roda em segundo plano
- Você pode fechar a aba e voltar depois para ver o andamento pela seção "Jobs recentes" do painel
- O resto do ProxOrchestrator continua funcionando durante a importação
- Várias importações podem rodar em paralelo (limitadas pela quantidade de workers do Celery)

## Se a importação falhar

Cada etapa mostra uma mensagem de erro se falhar. Falhas comuns:

**A conversão falha** — a imagem de disco de origem pode estar corrompida. Tente enviar o arquivo original de novo.

**VMID ocupado** — o VMID foi usado por outra VM entre a configuração e a implantação. Clique em "Tentar de novo" — um novo VMID será escolhido.

**A transferência SFTP falha** — normalmente é queda de rede ou falta de espaço no Proxmox. Confira o espaço livre no pool de destino.

**A importação do disco falha** — o pool pode não aceitar importação de qcow2 (pools LVM-thin, por exemplo, têm exigências próprias). Tente um armazenamento de pasta.

**Permissão negada** — a chave SSH não foi instalada direito. Rode o assistente de configuração de novo (passo 2).

Depois de qualquer falha, clique em **Tentar de novo** para recomeçar as etapas do início. As etapas que já deram certo não são retomadas — sempre começa do zero.
