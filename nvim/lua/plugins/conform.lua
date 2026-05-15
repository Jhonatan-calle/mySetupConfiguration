return {
  "stevearc/conform.nvim",
  opts = {
    formatters_by_ft = {
      c = { "clang_format" },
      cpp = { "clang_format" },
      objc = { "clang_format" },
      python = { "ruff_format", "ruff_organize_imports" },
    },

    formatters = {
      clang_format = {
        command = "clang-format",
        args = {
          "--style={BasedOnStyle: LLVM, ColumnLimit: 70, BinPackArguments: false, BinPackParameters: false, AlignAfterOpenBracket: AlwaysBreak, AllowAllArgumentsOnNextLine: false, AllowAllParametersOfDeclarationOnNextLine: false, PenaltyBreakBeforeFirstCallParameter: 1}",
        },
      },
    },
  },
}
