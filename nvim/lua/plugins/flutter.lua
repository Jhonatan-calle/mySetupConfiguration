return {
  "akinsho/flutter-tools.nvim",
  lazy = false,
  dependencies = {
    "nvim-lua/plenary.nvim",
    "stevearc/dressing.nvim", -- Opcional: mejora las ventanas de selección
  },
  config = function()
    require("flutter-tools").setup({
      ui = {
        notification_style = "native", -- O "telescope" si usas ese buscador
      },
      decorations = {
        statusline = {
          app_version = true,
          device = true,
        },
      },
      debugger = {
        enabled = true,
        run_via_dap = true, -- Integración con nvim-dap para depuración
      },
      lsp = {
        color = {
          enabled = true, -- Resalta los colores en el código (ej. Colors.blue)
        },
        settings = {
          showTodos = true,
          completeFunctionCalls = true,
        },
      },
    })
  end,
}
