import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';

/**
 * What a caller passes when opening the dialog. Exported so callers get
 * compile-time checking on the `data` object they hand to dialog.open().
 */
export interface ConfirmDialogData {
  title: string;
  message: string;
  /** Defaults to 'Confirm'. */
  confirmText?: string;
  /** Defaults to 'Cancel'. */
  cancelText?: string;
  /** Styles the confirm button as a warning. Use for deletes. */
  destructive?: boolean;
}

/**
 * Generic yes/no confirmation dialog.
 *
 * Open it and await the answer:
 *
 *   const confirmed = await firstValueFrom(
 *     this.dialog.open(ConfirmDialog, {
 *       data: { title: 'Delete?', message: '...', destructive: true },
 *     }).afterClosed(),
 *   );
 *
 * afterClosed() emits whatever value closed the dialog — `true` or `false`
 * from the buttons below, or `undefined` if the user pressed Escape or
 * clicked the backdrop. Treat anything falsy as "no".
 */
@Component({
  selector: 'app-confirm-dialog',
  imports: [MatDialogModule, MatButtonModule],
  templateUrl: './confirm-dialog.html',
  styleUrl: './confirm-dialog.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfirmDialog {
  // MAT_DIALOG_DATA is an injection token: MatDialog registers whatever you
  // passed as `data` under it, and this pulls it back out. The generic is a
  // promise to the type checker, not a runtime check.
  protected readonly data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
}
