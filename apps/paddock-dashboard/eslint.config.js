import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import vueTsEslintConfig from '@vue/eslint-config-typescript'

export default [
  { ignores: ['dist/**', 'node_modules/**', 'public/**'] },
  ...pluginVue.configs['flat/recommended'],
  ...vueTsEslintConfig(),
  {
    rules: {
      // Relax rules that conflict with the existing codebase style
      'vue/multi-word-component-names': 'off',           // Many components are single-word (e.g., Sprite)
      'vue/no-v-html': 'off',                            // Not used, but don't block future use
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'warn',       // Gradually remove remaining any usage
      'vue/require-default-prop': 'off',                  // Optional props don't need defaults in <script setup>
      'vue/singleline-html-element-content-newline': 'off',
      'vue/max-attributes-per-line': 'off',               // Prettier handles this
    }
  }
]
