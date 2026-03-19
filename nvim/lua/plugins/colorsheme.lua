return {
  {
    "folke/tokyonight.nvim",
    opts = {
      style = "storm", -- "night" también sirve. "day" es claro.
      styles = {
        comments = { italic = false },
        keywords = { italic = false },
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
