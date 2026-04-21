return {
  "neovim/nvim-lspconfig",
  opts = {
    servers = {
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
}
