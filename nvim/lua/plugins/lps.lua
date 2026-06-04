return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      inlay_hints = {
        enabled = false,
      },
      servers = {
        ts_ls = {},
        clangd = {
          on_attach = function(client)
            client.server_capabilities.documentFormattingProvider = false
            client.server_capabilities.documentRangeFormattingProvider = false
          end,
        },
        pyright = {
          settings = {
            python = {
              analysis = {
                typeCheckingMode = "basic",
                diagnosticSeverityOverrides = {
                  reportCallIssue = "none",
                  reportArgumentType = "none",
                  reportGeneralTypeIssues = "none",
                  reportOptionalMemberAccess = "none",
                  reportUnboundVariable = "warning",
                },
              },
            },
          },
        },
      },
    },
  },
}
