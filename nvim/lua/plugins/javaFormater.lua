#para esto hay que instalar google-java-format en mason
return {
  {
    "stevearc/conform.nvim",
    opts = {

      formatters_by_ft = {
        java = { "google-java-format" },
      },
      formatters = {
        prettier = {
          prepend_args = { "--print-width", "70" },
        },
      },
    },
  },
}
