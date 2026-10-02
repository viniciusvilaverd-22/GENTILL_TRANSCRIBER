# Gentill Transcriber 0.4.0-rc1 — Product upgrade

Esta fase transforma o projeto de um transcritor de arquivo único em um aplicativo desktop de uso contínuo.

## Recursos implementados

- drag-and-drop quando `tkinterdnd2` está disponível;
- seleção múltipla e fila sequencial;
- pausa, retomada e cancelamento cooperativo;
- progresso baseado no timestamp processado e duração da mídia;
- estimativa de tempo restante;
- seleção de modelos locais;
- gerenciador para download **explícito** de tiny/base/small/medium;
- exportação TXT, SRT, VTT, JSON e DOCX;
- histórico local em SQLite, sem armazenar o texto transcrito;
- diagnóstico de CPU, RAM, backend e fator de tempo real;
- diarização opcional com pyannote.audio e pipeline local;
- Portable Full Offline;
- instalador Windows por usuário;
- desinstalador registrado em HKCU;
- variante Lite sem modelo embutido;
- pipeline de assinatura Authenticode opcional.

## Assinatura

A assinatura só é ativada quando a variável de ambiente `GENTILL_SIGN_CERT_SHA1` aponta para um certificado Authenticode válido disponível no Windows.

Sem certificado, o build registra:

`WINDOWS_SIGNING=SKIPPED`

Nenhum certificado autoassinado é criado para simular confiança pública.

## Diarização

A release padrão não incorpora pyannote/torch porque isso aumentaria substancialmente o tamanho e exigiria um pipeline específico/licenciado.

Para desenvolvimento:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-diarization.txt
```

Depois escolha um pipeline provisionado localmente na interface. A transcrição continua sem downloads automáticos.
