return {
  "mason-org/mason.nvim",
  opts = { ensure_installed = {
      "prettier",
      "ruff",
      "pyright",
      "black",
      "debugpy",
    },
  },
}
