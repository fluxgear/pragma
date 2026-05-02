<template>
  <div class="rich-text-editor" :class="{ 'rich-text-editor--disabled': disabled }">
    <div class="rich-text-editor__toolbar">
      <Button
        type="button"
        label="Paragraph"
        size="small"
        :disabled="disabled"
        :severity="isParagraphActive ? 'contrast' : 'secondary'"
        :aria-pressed="isParagraphActive"
        variant="outlined"
        @click="setParagraph"
      />
      <Button
        type="button"
        label="H2"
        size="small"
        :disabled="disabled"
        :severity="isHeadingTwoActive ? 'contrast' : 'secondary'"
        :aria-pressed="isHeadingTwoActive"
        variant="outlined"
        @click="toggleHeading(2)"
      />
      <Button
        type="button"
        label="H3"
        size="small"
        :disabled="disabled"
        :severity="isHeadingThreeActive ? 'contrast' : 'secondary'"
        :aria-pressed="isHeadingThreeActive"
        variant="outlined"
        @click="toggleHeading(3)"
      />
      <Button
        type="button"
        icon="pi pi-bold"
        aria-label="Bold"
        size="small"
        :disabled="disabled"
        :severity="isBoldActive ? 'contrast' : 'secondary'"
        :aria-pressed="isBoldActive"
        variant="outlined"
        @click="toggleBold"
      />
      <Button
        type="button"
        icon="pi pi-italic"
        aria-label="Italic"
        size="small"
        :disabled="disabled"
        :severity="isItalicActive ? 'contrast' : 'secondary'"
        :aria-pressed="isItalicActive"
        variant="outlined"
        @click="toggleItalic"
      />
      <Button
        type="button"
        label="Strike"
        size="small"
        :disabled="disabled"
        :severity="isStrikeActive ? 'contrast' : 'secondary'"
        :aria-pressed="isStrikeActive"
        variant="outlined"
        @click="toggleStrike"
      />
      <Button
        type="button"
        label="Quote"
        size="small"
        :disabled="disabled"
        :severity="isBlockquoteActive ? 'contrast' : 'secondary'"
        :aria-pressed="isBlockquoteActive"
        variant="outlined"
        @click="toggleBlockquote"
      />
      <Button
        type="button"
        label="Bullets"
        size="small"
        :disabled="disabled"
        :severity="isBulletListActive ? 'contrast' : 'secondary'"
        :aria-pressed="isBulletListActive"
        variant="outlined"
        @click="toggleBulletList"
      />
      <Button
        type="button"
        label="Numbers"
        size="small"
        :disabled="disabled"
        :severity="isOrderedListActive ? 'contrast' : 'secondary'"
        :aria-pressed="isOrderedListActive"
        variant="outlined"
        @click="toggleOrderedList"
      />
      <Button
        type="button"
        label="Code"
        size="small"
        :disabled="disabled"
        :severity="isCodeBlockActive ? 'contrast' : 'secondary'"
        :aria-pressed="isCodeBlockActive"
        variant="outlined"
        @click="toggleCodeBlock"
      />
      <Button
        type="button"
        label="Rule"
        size="small"
        :disabled="disabled"
        severity="secondary"
        variant="outlined"
        @click="insertHorizontalRule"
      />
      <Button
        type="button"
        icon="pi pi-undo"
        aria-label="Undo"
        size="small"
        :disabled="disabled || !canUndo"
        severity="secondary"
        variant="outlined"
        @click="undo"
      />
      <Button
        type="button"
        icon="pi pi-replay"
        aria-label="Redo"
        size="small"
        :disabled="disabled || !canRedo"
        severity="secondary"
        variant="outlined"
        @click="redo"
      />
    </div>

    <EditorContent :editor="editor" class="rich-text-editor__content" />

    <small class="muted rich-text-editor__hint">
      Stored output is restricted to the Pragma rich-text HTML contract: paragraphs, headings, emphasis, lists, blockquotes, code, hard breaks, and horizontal rules.
    </small>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import Button from 'primevue/button'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/vue-3'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    disabled?: boolean
    inputId?: string
    ariaLabelledby?: string
  }>(),
  {
    modelValue: '',
    disabled: false,
    inputId: undefined,
    ariaLabelledby: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function editorAccessibilityAttributes(): Record<string, string> {
  const attributes: Record<string, string> = {
    class: 'tiptap rich-text-editor__input',
    role: 'textbox',
    'aria-multiline': 'true',
    spellcheck: 'true',
  }

  if (props.inputId) {
    attributes.id = props.inputId
  }
  if (props.ariaLabelledby) {
    attributes['aria-labelledby'] = props.ariaLabelledby
  }

  return attributes
}

function applyEditorAccessibilityAttributes(): void {
  const element = editor.value?.view.dom
  if (!element) {
    return
  }

  for (const [name, value] of Object.entries(editorAccessibilityAttributes())) {
    element.setAttribute(name, value)
  }

  if (!props.inputId) {
    element.removeAttribute('id')
  }
  if (!props.ariaLabelledby) {
    element.removeAttribute('aria-labelledby')
  }
}

const editor = useEditor({
  content: props.modelValue,
  editable: !props.disabled,
  immediatelyRender: false,
  extensions: [StarterKit],
  editorProps: {
    attributes: editorAccessibilityAttributes(),
  },
  onUpdate: ({ editor: currentEditor }) => {
    emit('update:modelValue', currentEditor.getHTML())
  },
})

const isParagraphActive = computed(() => editor.value?.isActive('paragraph') ?? false)
const isHeadingTwoActive = computed(() => editor.value?.isActive('heading', { level: 2 }) ?? false)
const isHeadingThreeActive = computed(() => editor.value?.isActive('heading', { level: 3 }) ?? false)
const isBoldActive = computed(() => editor.value?.isActive('bold') ?? false)
const isItalicActive = computed(() => editor.value?.isActive('italic') ?? false)
const isStrikeActive = computed(() => editor.value?.isActive('strike') ?? false)
const isBlockquoteActive = computed(() => editor.value?.isActive('blockquote') ?? false)
const isBulletListActive = computed(() => editor.value?.isActive('bulletList') ?? false)
const isOrderedListActive = computed(() => editor.value?.isActive('orderedList') ?? false)
const isCodeBlockActive = computed(() => editor.value?.isActive('codeBlock') ?? false)
const canUndo = computed(() => editor.value?.can().chain().focus().undo().run() ?? false)
const canRedo = computed(() => editor.value?.can().chain().focus().redo().run() ?? false)

watch(
  () => props.modelValue,
  (value) => {
    const currentEditor = editor.value
    if (!currentEditor) {
      return
    }

    const nextValue = value ?? ''
    if (currentEditor.getHTML() === nextValue) {
      return
    }

    currentEditor.commands.setContent(nextValue, false)
  },
)

watch(
  () => props.disabled,
  (value) => {
    editor.value?.setEditable(!value)
  },
)

watch([editor, () => props.inputId, () => props.ariaLabelledby], () => {
  applyEditorAccessibilityAttributes()
}, { immediate: true })

function setParagraph(): void {
  editor.value?.chain().focus().setParagraph().run()
}

function toggleHeading(level: 2 | 3): void {
  editor.value?.chain().focus().toggleHeading({ level }).run()
}

function toggleBold(): void {
  editor.value?.chain().focus().toggleBold().run()
}

function toggleItalic(): void {
  editor.value?.chain().focus().toggleItalic().run()
}

function toggleStrike(): void {
  editor.value?.chain().focus().toggleStrike().run()
}

function toggleBlockquote(): void {
  editor.value?.chain().focus().toggleBlockquote().run()
}

function toggleBulletList(): void {
  editor.value?.chain().focus().toggleBulletList().run()
}

function toggleOrderedList(): void {
  editor.value?.chain().focus().toggleOrderedList().run()
}

function toggleCodeBlock(): void {
  editor.value?.chain().focus().toggleCodeBlock().run()
}

function insertHorizontalRule(): void {
  editor.value?.chain().focus().setHorizontalRule().run()
}

function undo(): void {
  editor.value?.chain().focus().undo().run()
}

function redo(): void {
  editor.value?.chain().focus().redo().run()
}

onBeforeUnmount(() => {
  editor.value?.destroy()
})

defineExpose({ editor })
</script>
