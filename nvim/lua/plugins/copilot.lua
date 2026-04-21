return {
  "zbirenbaum/copilot.lua",
  cmd = "Copilot",
  build = ":Copilot auth",
  event = "BufReadPost",
  opts = {
    suggestion = {
      enabled = true,
      auto_trigger = true,       -- show suggestions automatically
      hide_during_completion = true,
      keymap = {
        accept = "<C-l>",
        next = "<M-]>",          -- next suggestion
        prev = "<M-[>",          -- previous suggestion
        dismiss = "<C-e>",       -- ignore suggestion
      },
    },
    filetypes = {
      markdown = true,
      help = true,
    },
  },
}
