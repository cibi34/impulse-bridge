<script lang="ts" module>
	export interface Problem {
		line: number | null;
		message: string;
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { basicSetup } from 'codemirror';
	import { EditorView } from '@codemirror/view';
	import { EditorState } from '@codemirror/state';
	import { yaml } from '@codemirror/lang-yaml';
	import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
	import { lintGutter, setDiagnostics, type Diagnostic } from '@codemirror/lint';
	import { tags } from '@lezer/highlight';

	let {
		value = $bindable(''),
		problems = [],
		label
	}: { value?: string; problems?: Problem[]; label: string } = $props();

	let host: HTMLDivElement;
	let view: EditorView | undefined;

	// Colours come from the design tokens, so the editor follows the theme.
	const theme = EditorView.theme({
		'&': {
			height: '100%',
			backgroundColor: 'var(--editor-bg)',
			color: 'var(--text)',
			fontSize: '13px'
		},
		'.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.6' },
		'.cm-content': { caretColor: 'var(--accent-text)', padding: '12px 0' },
		'.cm-gutters': {
			backgroundColor: 'var(--editor-bg)',
			color: 'var(--text-3)',
			border: 'none',
			borderRight: '1px solid var(--separator)'
		},
		'.cm-activeLine': { backgroundColor: 'var(--editor-active-line)' },
		'.cm-activeLineGutter': {
			backgroundColor: 'var(--editor-active-line)',
			color: 'var(--text-2)'
		},
		'&.cm-focused': { outline: '2px solid var(--focus)', outlineOffset: '-2px' },
		'&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
			backgroundColor: 'rgb(143 184 230 / 0.25)'
		},
		'.cm-cursor': { borderLeftColor: 'var(--accent-text)' },
		'.cm-tooltip': {
			backgroundColor: 'var(--bg-elevated)',
			color: 'var(--text)',
			border: '1px solid var(--separator-strong)',
			borderRadius: '8px'
		},
		'.cm-diagnostic-error': { borderLeftColor: 'var(--danger-text)' },
		'.cm-lintRange-error': {
			backgroundImage: 'none',
			textDecoration: 'underline wavy var(--danger-text)',
			textUnderlineOffset: '3px'
		}
	});

	const highlight = HighlightStyle.define([
		{ tag: [tags.propertyName, tags.definition(tags.propertyName)], color: 'var(--link)' },
		{ tag: [tags.string, tags.special(tags.string)], color: 'var(--success-text)' },
		{ tag: [tags.number, tags.bool, tags.null], color: 'var(--warning-text)' },
		{ tag: tags.comment, color: 'var(--text-3)', fontStyle: 'italic' },
		{ tag: [tags.punctuation, tags.separator], color: 'var(--text-2)' },
		{ tag: [tags.keyword, tags.labelName], color: 'var(--accent-text)' }
	]);

	onMount(() => {
		view = new EditorView({
			parent: host,
			state: EditorState.create({
				doc: value,
				extensions: [
					basicSetup,
					yaml(),
					theme,
					syntaxHighlighting(highlight),
					lintGutter(),
					EditorView.lineWrapping,
					// An explicit tabindex marks the scrolling editor as keyboard-reachable.
					EditorView.contentAttributes.of({ 'aria-label': label, tabindex: '0' }),
					EditorView.updateListener.of((update) => {
						if (update.docChanged) value = update.state.doc.toString();
					})
				]
			})
		});
		return () => view?.destroy();
	});

	// Load a different text from outside (another file, a revert).
	$effect(() => {
		const next = value;
		if (view && next !== view.state.doc.toString()) {
			view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next } });
		}
	});

	// Show validation problems on their lines.
	$effect(() => {
		if (!view) return;
		const doc = view.state.doc;
		const diagnostics: Diagnostic[] = problems
			.filter((p) => p.line !== null && p.line >= 1 && p.line <= doc.lines)
			.map((p) => {
				const line = doc.line(p.line as number);
				return {
					from: line.from,
					to: Math.max(line.from, line.to),
					severity: 'error',
					message: p.message
				};
			});
		view.dispatch(setDiagnostics(view.state, diagnostics));
	});

	/** Move the cursor to a line and focus the editor. */
	export function goToLine(lineNumber: number) {
		if (!view) return;
		const line = view.state.doc.line(Math.min(Math.max(1, lineNumber), view.state.doc.lines));
		view.dispatch({ selection: { anchor: line.from }, scrollIntoView: true });
		view.focus();
	}
</script>

<div class="editor" bind:this={host}></div>

<style>
	.editor {
		height: 100%;
		min-height: 360px;
		border-radius: var(--radius);
		overflow: hidden;
		border: 1px solid var(--separator-strong);
	}

	.editor :global(.cm-editor) {
		height: 100%;
	}
</style>
