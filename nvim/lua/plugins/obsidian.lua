return {
  "epwalsh/obsidian.nvim",
  version = "*",
  lazy = true,
  ft = "markdown",
  dependencies = {
    "nvim-lua/plenary.nvim",
    -- No necesitas poner "hrsh7th/nvim-cmp" aquí porque usas blink.cmp
  },
  config = function()
    require("obsidian").setup({
      workspaces = {
        { name = "personal", path = "/home/jhonatan/OneDrive/" },
      },
      -- CAMBIO CRÍTICO: Desactivamos nvim_cmp aquí para que no busque el módulo
    })
  end,
}
