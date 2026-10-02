# Privacidade e comportamento offline

O Gentill Transcriber foi projetado para processamento local.

## Garantias do runtime

- nenhuma chave de API de transcrição é necessária;
- áudio e vídeo são enviados ao runtime local do faster-whisper;
- o modelo Whisper é carregado do disco;
- o carregamento do modelo usa `local_files_only=True`;
- TXT, JSON, SRT e VTT são gravados na máquina do usuário.

## O que pode usar internet

Durante desenvolvimento ou build, a internet pode ser usada para instalar dependências e baixar o modelo antes do uso offline. O script de build do macOS também pode provisionar o modelo quando ele não existir.

Isso é separado do caminho normal de transcrição.

## Higiene do repositório

O repositório público exclui:

- pesos do modelo;
- ambientes virtuais;
- mídia do usuário;
- transcrições geradas;
- diretórios de build;
- bundles de release;
- logs, auditorias e receipts locais.

## Modelo de ameaça

O foco atual é evitar transcrição acidental em nuvem e downloads implícitos do modelo. O projeto não é apresentado como sandbox de segurança para arquivos maliciosos nem substitui proteção do sistema operacional.
