export interface Toast {
	id: number;
	message: string;
	kind: 'info' | 'success' | 'error';
	action?: { label: string; run: () => void };
}

class Toasts {
	items = $state<Toast[]>([]);
	private nextId = 1;

	show(message: string, options: { kind?: Toast['kind']; action?: Toast['action'] } = {}): void {
		const toast: Toast = {
			id: this.nextId++,
			message,
			kind: options.kind ?? 'info',
			action: options.action
		};
		this.items = [...this.items.slice(-2), toast];
		// Long enough to read and to reach an action button with the keyboard.
		const timeout = toast.action ? 8000 : toast.kind === 'error' ? 7000 : 4000;
		setTimeout(() => this.dismiss(toast.id), timeout);
	}

	success(message: string, action?: Toast['action']): void {
		this.show(message, { kind: 'success', action });
	}

	error(message: string): void {
		this.show(message, { kind: 'error' });
	}

	dismiss(id: number): void {
		this.items = this.items.filter((t) => t.id !== id);
	}
}

export const toasts = new Toasts();
