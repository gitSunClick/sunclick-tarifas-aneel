/**
 * Code.gs — duas responsabilidades:
 *
 *   1. Recebe atualizações de tarifas via HTTP POST (doPost) e escreve na
 *      aba TARIFAS_SUNCLICK da planilha à qual este script está VINCULADO
 *      (Extensões > Apps Script, dentro da própria planilha). Quem chama
 *      isso é o workflow do GitHub Actions, depois de calcular as tarifas
 *      vigentes. Não precisa de service account nem de OAuth Client ID no
 *      Google Cloud Console — só a autorização normal que você concede ao
 *      publicar o Web App.
 *
 *   2. Adiciona um botão/menu "⚡ SUNCLICK" na própria planilha (igual ao
 *      processo antigo) que, ao ser clicado, dispara sob demanda o mesmo
 *      workflow do GitHub Actions — pra quando alguém sabe que saiu uma
 *      resolução nova e não quer esperar o próximo agendamento (ou quando
 *      não há agendamento automático nenhum, como é o caso atual: a
 *      atualização só acontece quando alguém clica no botão).
 *
 * COMO CONFIGURAR (resumo — detalhes no LEIA-ME.md):
 *   1. Na planilha do Google Sheets, vá em Extensões > Apps Script.
 *   2. Apague o conteúdo padrão de Code.gs e cole este arquivo inteiro.
 *   3. Troque TOKEN_ESPERADO abaixo por um token secreto (uma string
 *      aleatória qualquer, só você precisa saber).
 *   4. Preencha GITHUB_OWNER / GITHUB_REPO / GITHUB_WORKFLOW abaixo com os
 *      dados do seu repositório (já preenchidos com os valores atuais).
 *   5. Implantar > Nova implantação > tipo "Aplicativo da Web".
 *      - Executar como: Eu (sua conta)
 *      - Quem pode acessar: Qualquer pessoa
 *   6. Autorize o script quando pedido (é a sua própria conta autorizando
 *      o próprio script a editar a própria planilha).
 *   7. Copie a URL do Web App gerada — é o valor de GOOGLE_APPS_SCRIPT_URL
 *      usado nos secrets do GitHub.
 *   8. Use o MESMO token do passo 3 como GOOGLE_APPS_SCRIPT_TOKEN nos
 *      secrets do GitHub.
 *   9. Pra o botão funcionar, crie um GitHub Personal Access Token (veja
 *      LEIA-ME.md) e salve em Configurações do projeto (ícone de
 *      engrenagem) > Propriedades do script > adicionar propriedade
 *      GITHUB_TOKEN com o valor do token. NÃO cole o token direto no
 *      código — é por isso que fica nas Propriedades do Script, que só
 *      você (dona do script) consegue ver.
 *  10. Feche e reabra a planilha (ou recarregue a página) — o menu
 *      "⚡ SUNCLICK" aparece na barra de menus, ao lado de Ajuda.
 */

var TOKEN_ESPERADO = "TROQUE_ISTO_POR_UM_TOKEN_SECRETO_SEU";

// Dados do repositório do GitHub onde está o script Python + o workflow.
var GITHUB_OWNER = "gitSunClick";
var GITHUB_REPO = "sunclick-tarifas-aneel";
var GITHUB_WORKFLOW = "atualizar_tarifas.yml";
var GITHUB_BRANCH = "main";

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

    // idem para a coluna de timestamp (data/hora da última tentativa de
    // atualização) — opcional: só existe se o Python mandar
    // "coluna_timestamp" no payload (versões antigas do script não mandam).
    var colTimestampIdx = -1;
    if (dados.coluna_timestamp) {
      colTimestampIdx = cabecalho.indexOf(dados.coluna_timestamp);
      if (colTimestampIdx === -1) {
        colTimestampIdx = cabecalho.length;
        aba.getRange(1, colTimestampIdx + 1).setValue(dados.coluna_timestamp);
        cabecalho.push(dados.coluna_timestamp);
        ultimaColuna = cabecalho.length;
      }
    }

    // valores da coluna-chave, SEM o cabeçalho (linha 2 em diante)
    var numLinhasDados = Math.max(ultimaLinha - 1, 0);
    var chavesPlanilha = numLinhasDados > 0
      ? aba.getRange(2, colChaveIdx + 1, numLinhasDados, 1).getValues().map(function (r) { return r[0]; })
      : [];

    // Limpa status/timestamp de TODAS as linhas antes de começar a gravar de
    // novo — assim, se uma distribuidora sumir do config.py (ou o payload
    // vier incompleto por algum motivo), a linha correspondente fica em
    // branco em vez de continuar mostrando um status antigo enganoso. Os
    // valores de tarifa (TUSD/TE/etc.) NÃO são tocados aqui — só status e
    // timestamp, que são recalculados do zero a cada atualização de qualquer
    // forma.
    if (numLinhasDados > 0) {
      var brancoStatus = [];
      for (var i = 0; i < numLinhasDados; i++) brancoStatus.push(['']);
      aba.getRange(2, colStatusIdx + 1, numLinhasDados, 1).setValues(brancoStatus);
      if (colTimestampIdx !== -1) {
        aba.getRange(2, colTimestampIdx + 1, numLinhasDados, 1).setValues(brancoStatus);
      }
    }

    // Um único timestamp pra todas as linhas desta execução (não teria
    // sentido cada linha ter um segundo diferente) — no fuso horário
    // configurado na própria planilha.
    var agora = Utilities.formatDate(new Date(), planilha.getSpreadsheetTimeZone(), "dd/MM/yyyy HH:mm");

    var atualizadas = 0;
    var naoEncontradas = [];

    (dados.linhas || []).forEach(function (linha) {
      var pos = chavesPlanilha.indexOf(linha.chave); // 0-based; pos 0 = linha 2 da planilha
      if (pos === -1) {
        naoEncontradas.push(linha.chave);
        return;
      }
      var linhaPlanilha = pos + 2; // 1-based, já compensando o cabeçalho

      // status e timestamp sempre são atualizados (mesmo em pendência —
      // é útil saber QUANDO a última tentativa rodou, mesmo sem sucesso)
      aba.getRange(linhaPlanilha, colStatusIdx + 1).setValue(linha.status_texto);
      if (colTimestampIdx !== -1) {
        aba.getRange(linhaPlanilha, colTimestampIdx + 1).setValue(agora);
      }

      // regra do handoff: nunca apagar valor existente numa pendência —
      // só grava campos quando a linha veio com algo em "campos"
      var campos = linha.campos || {};
      Object.keys(campos).forEach(function (nomeColuna) {
        var colIdx = cabecalho.indexOf(nomeColuna);
        if (colIdx === -1) {
          // coluna nova (ex.: TRCI, TC, Valor dos Tributos etc.) — cria no
          // final da planilha em vez de ignorar, igual já fazíamos pra
          // status/timestamp. Assim uma coluna nova adicionada no Python
          // (config.COLUNAS_PLANILHA) aparece sozinha, sem precisar criar
          // manualmente na planilha antes.
          colIdx = cabecalho.length;
          aba.getRange(1, colIdx + 1).setValue(nomeColuna);
          cabecalho.push(nomeColuna);
          ultimaColuna = cabecalho.length;
        }
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

// ---------------------------------------------------------------------------
// Botão "⚡ SUNCLICK" na planilha — dispara a atualização sob demanda
// ---------------------------------------------------------------------------

// onOpen roda automaticamente toda vez que a planilha é aberta e cria o menu.
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("⚡ SUNCLICK")
    .addItem("🔄 Atualizar Tarifas ANEEL", "dispararAtualizacaoTarifas")
    .addToUi();
}

// Chamado pelo item de menu. Não calcula nada aqui — só pede pro GitHub
// Actions rodar o workflow que já faz todo o trabalho (baixar da ANEEL,
// filtrar, escrever na planilha via doPost acima). Por isso a atualização
// não aparece instantaneamente: leva cerca de 1 a 2 minutos rodando na
// nuvem do GitHub, igual levaria rodando local.
function dispararAtualizacaoTarifas() {
  var ui = SpreadsheetApp.getUi();
  var token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");

  if (!token) {
    ui.alert(
      "Falta configurar",
      "Não encontrei o GITHUB_TOKEN nas Propriedades do Script. Veja o " +
        "passo 9 do cabeçalho deste arquivo (Code.gs) ou o apps_script/LEIA-ME.md.",
      ui.ButtonSet.OK
    );
    return;
  }

  var url =
    "https://api.github.com/repos/" + GITHUB_OWNER + "/" + GITHUB_REPO +
    "/actions/workflows/" + GITHUB_WORKFLOW + "/dispatches";

  var resposta = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token,
      Accept: "application/vnd.github+json",
    },
    payload: JSON.stringify({ ref: GITHUB_BRANCH }),
    muteHttpExceptions: true,
  });

  var status = resposta.getResponseCode();
  if (status === 204) {
    ui.alert(
      "Atualização disparada ✅",
      "Pedido enviado com sucesso. A ANEEL costuma levar 1 a 2 minutos pra " +
        "processar e atualizar as células — pode fechar esse aviso e conferir " +
        "a planilha daqui a pouco. Se quiser acompanhar em tempo real, é na " +
        "aba Actions do repositório no GitHub.",
      ui.ButtonSet.OK
    );
  } else {
    ui.alert(
      "Erro ao disparar (" + status + ")",
      "Resposta do GitHub: " + resposta.getContentText().substring(0, 500) +
        "\n\nCausas comuns: token do GitHub inválido/expirado, ou sem permissão " +
        "de Actions nesse repositório.",
      ui.ButtonSet.OK
    );
  }
}
