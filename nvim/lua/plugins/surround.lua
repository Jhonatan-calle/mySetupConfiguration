-- esto es para comillas, paréntesis, corchetes, etc. alrededor de texto seleccionado o para cambiar el tipo de delimitadores alrededor del texto. Es una herramienta muy útil para editar código y texto de manera eficiente.
return {
  "kylechui/nvim-surround",
  version = "*", -- Usa la última versión estable
  event = "VeryLazy",
  config = function()
    require("nvim-surround").setup({
      surrounds = {
        ["m"] = {
          add = { "**", "**" },
        },
      },
    })
  end,
}
