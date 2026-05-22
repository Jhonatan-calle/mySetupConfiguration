return {
  {
    "folke/tokyonight.nvim",
    opts = {
      style = "night", -- "night" también sirve. "day" es claro.
      styles = {
        keywords = { italic = false, bold = false },
        functions = { bold = false },
        variables = { bold = false },
      },
      -- puedes subir contraste del sidebar/floats:
      sidebars = "dark",
      floats = "dark",
    },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "tokyonight",
    },
  },
}
