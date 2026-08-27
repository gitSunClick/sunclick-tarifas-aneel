/**
 * Code.gs — recebe atualizações de tarifas via HTTP POST e escreve na aba
 * TARIFAS_SUNCLICK (ou outra que você passar) da planilha à qual este
 * script está VINCULADO (Extensões > Apps Script, dentro da própria
 * planilha). Não precisa de service account nem de OAuth Client ID no
 * Google Cloud Console — só a autorização normal que você concede ao
 * publicar o Web App.
 *
 * COMO CONFIGURAR (resumo — detalhes no LEIA-ME.md):
 *   1. Na planilha do Google Sheets, vá em Extensões > Apps Script.
 *   2. Apague o conteúdo padrão de Code.gs e cole este arquivo inteiro.
 *   3. Troque TOKEN_ESPERADO abaixo por um token secreto (uma string
 *      aleatória qualquer, só você precisa saber).
 *   4. Implantar > Nova implantação > tipo "Aplicativo da Web".
 *      - Executar como: Eu (sua conta)
 *      - Quem pode acessar: Qualquer pessoa
 *   5. Autorize o script quando pedido (é a sua própria conta autorizando
 *      o próprio script a editar a própria planilha).
 *   6. Copie a URL do Web App gerada — é o valor de GOOGLE_APPS_SCRIPT_URL.
 *   7. Use o MESMO token do passo 3 como GOOGLE_APPS_SCRIPT_TOKEN.
 */

var TOKEN_ESPERADO = "TROQUE_ISTO_POR_UM_TOKEN_SECRETO_SEU";

function doPost(e) {
  try {
    var dados = JSON.parse(e.postData.contents);

    if (dados.token !== TOKEN_ESPERADO) {
      return respostaJson({ erro: "token inválido" });
    }

    var planilha = SpreadsheetApp.getActiveSpreadsheet();
    var aba = planilha.getSheetByName(dados.worksheet);
    if (!aba) {
      return respostaJson({ erro: "aba não encontrada: " + dados.worksheet });
    }

    var ultimaColuna = aba.getLastColumn();
    var ultimaLinha = aba.getLastRow();
    var cabecalho = aba.getRange(1, 1, 1, ultimaColuna).getValues()[0];

    var colChaveIdx = cabecalho.indexOf(dados.coluna_chave);
    if (colChaveIdx === -1) {
      return respostaJson({ erro: "coluna-chave não encontrada: " + dados.coluna_chave });
    }

    // garante que a coluna de status existe (cria no final se faltar)
    var colStatusIdx = cabecalho.indexOf(dados.coluna_status);
    if (colStatusIdx === -1) {
      colStatusIdx = cabecalho.length;
      aba.getRange(1, colStatusIdx + 1).setValue(dados.coluna_status);
      cabecalho.push(dados.coluna_status);
      ultimaColuna = cabecalho.length;
    }

    // valores da coluna-chave, SEM o cabeçalho (linha 2 em diante)
    var numLinhasDados = Math.max(ultimaLinha - 1, 0);
    var chavesPlanilha = numLinhasDados > 0
      ? aba.getRange(2, colChaveIdx + 1, numLinhasDados, 1).getValues().map(function (r) { return r[0]; })
      : [];

    var atualizadas = 0;
    var naoEncontradas = [];

    (dados.linhas || []).forEach(function (linha) {
      var pos = chavesPlanilha.indexOf(linha.chave); // 0-based; pos 0 = linha 2 da planilha
      if (pos === -1) {
        naoEncontradas.push(linha.chave);
        return;
      }
      var linhaPlanilha = pos + 2; // 1-based, já compensando o cabeçalho

      // status sempre é atualizado
      aba.getRange(linhaPlanilha, colStatusIdx + 1).setValue(linha.status_texto);

      // regra do handoff: nunca apagar valor existente numa pendência —
      // só grava campos quando a linha veio com algo em "campos"
      var campos = linha.campos || {};
      Object.keys(campos).forEach(function (nomeColuna) {
        var colIdx = cabecalho.indexOf(nomeColuna);
        if (colIdx === -1) return; // coluna não existe na planilha, ignora
        aba.getRange(linhaPlanilha, colIdx + 1).setValue(campos[nomeColuna]);
      });

      atualizadas++;
    });

    return respostaJson({
      ok: true,
      atualizadas: atualizadas,
      nao_encontradas: naoEncontradas,
    });
  } catch (err) {
    return respostaJson({ erro: String(err) });
  }
}

// GET só pra você conseguir testar a URL no navegador e ver que está no ar
function doGet(e) {
  return respostaJson({ ok: true, info: "Web App ativo. Use POST para atualizar a planilha." });
}

function respostaJson(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
