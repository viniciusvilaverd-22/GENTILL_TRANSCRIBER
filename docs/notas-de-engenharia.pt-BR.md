# Notas de engenharia

## Estudo de caso: bug presente apenas no executável empacotado

Durante a preparação da release Windows apareceu um problema importante de QA.

### Sintoma

O aplicativo empacotado falhava durante a transcrição com:

```text
open() got an unexpected keyword argument 'metadata_errors'
```

Ao mesmo tempo, os testes do código-fonte estavam passando.

### Causa raiz

Um executável antigo continha uma versão do PyAV em que `av.open()` não expunha o argumento `metadata_errors` utilizado pelo `faster-whisper 1.2.1`.

O processo de QA provava que a interface abria, mas ainda não provava que a decodificação de mídia funcionava dentro do artefato PyInstaller.

### Correção

O processo passou a:

1. fixar a dependência de runtime compatível;
2. chamar de verdade `av.open(..., metadata_errors="ignore")` em teste;
3. oferecer um modo de self-test no executável;
4. gerar um WAV de teste;
5. transcrever esse WAV pelo `.exe`;
6. exigir TXT, JSON, SRT e VTT antes de promover o RC.

### Resultado

O limite de confiança deixou de ser apenas o source Python e passou a ser o **artefato desktop final**.

Esse caso demonstra debugging de dependências nativas, diferença entre runtime de desenvolvimento e bundle, e evolução de testes para E2E orientado ao produto.
