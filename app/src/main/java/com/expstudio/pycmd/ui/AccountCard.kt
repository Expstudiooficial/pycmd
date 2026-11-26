package com.expstudio.pycmd.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

/**
 * A PyCmd account on the Teach tab: sign in, and lessons follow you between
 * the phone and PyCmd for Windows. The password is stretched in Python
 * (pycmd_teach/cloud.py) before anything leaves the phone; nothing here does
 * more than hand it over.
 */
data class TeachAccount(
    val signedIn: Boolean = false,
    val username: String = "",
    /** Seconds since 1970 of the last good sync; 0 for never. */
    val syncedAt: Long = 0,
    val syncing: Boolean = false,
    val lastError: String = "",
    /** A sign-in, sign-up or password change is on its way. */
    val busy: Boolean = false,
    /** What the open dialog should say went wrong; empty when nothing did. */
    val formError: String = "",
    /** The answer to "is this username free", for the name being typed. */
    val nameCheck: NameCheck? = null,
)

data class NameCheck(val name: String, val available: Boolean, val reason: String)

/** Everything the account card can ask for, in one place. */
class AccountActions(
    val signIn: (String, String) -> Unit = { _, _ -> },
    val signUp: (String, String) -> Unit = { _, _ -> },
    val checkName: (String) -> Unit = {},
    val sync: () -> Unit = {},
    val signOut: () -> Unit = {},
    val changePassword: (String, String) -> Unit = { _, _ -> },
    val delete: (String) -> Unit = {},
    val export: () -> Unit = {},
    /** "merge" or "replace": the file picker opens after. */
    val import: (String) -> Unit = {},
    val clearError: () -> Unit = {},
)

fun syncedText(seconds: Long): String {
    if (seconds <= 0) return "not synced yet"
    val ago = (System.currentTimeMillis() / 1000 - seconds).coerceAtLeast(0)
    return when {
        ago < 45 -> "synced just now"
        ago < 90 -> "synced a minute ago"
        ago < 3600 -> "synced ${ago / 60} minutes ago"
        ago < 5400 -> "synced an hour ago"
        ago < 86400 -> "synced ${ago / 3600} hours ago"
        else -> "synced ${ago / 86400} days ago"
    }
}

private enum class AccountDialog { NONE, SIGN_IN, SIGN_UP, MANAGE, IMPORT }

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AccountCard(account: TeachAccount, actions: AccountActions) {
    var dialog by remember { mutableStateOf(AccountDialog.NONE) }
    // A successful sign-in closes its dialog: the card flips to signed in.
    LaunchedEffect(account.signedIn) {
        if (account.signedIn && (dialog == AccountDialog.SIGN_IN || dialog == AccountDialog.SIGN_UP)) {
            dialog = AccountDialog.NONE
        }
        if (!account.signedIn && dialog == AccountDialog.MANAGE) dialog = AccountDialog.NONE
    }

    PyCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(
                        if (account.signedIn) {
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.16f)
                        } else {
                            MaterialTheme.colorScheme.surfaceVariant
                        },
                    )
                    .border(1.dp, MaterialTheme.colorScheme.outline, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                if (account.signedIn) {
                    Text(
                        account.username.take(1).uppercase(),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                } else {
                    Icon(
                        PyIcons.Cloud,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    if (account.signedIn) account.username else "Keep your progress everywhere",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    when {
                        !account.signedIn ->
                            "Sign in and your lessons follow you between this phone and " +
                                "PyCmd for Windows."
                        account.syncing -> "Syncing…"
                        account.lastError.isNotEmpty() -> "Not synced: ${account.lastError}"
                        else -> "Progress ${syncedText(account.syncedAt)}"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (account.lastError.isNotEmpty() && account.signedIn) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (account.signedIn) {
                ActionButton(
                    if (account.syncing) "Syncing" else "Sync",
                    PyIcons.Sync,
                    onClick = actions.sync,
                    enabled = !account.syncing,
                )
                GhostButton("Account", PyIcons.Person, onClick = {
                    actions.clearError()
                    dialog = AccountDialog.MANAGE
                })
            } else {
                ActionButton("Sign in", PyIcons.Person, onClick = {
                    actions.clearError()
                    dialog = AccountDialog.SIGN_IN
                })
                GhostButton("Create account", PyIcons.Add, onClick = {
                    actions.clearError()
                    dialog = AccountDialog.SIGN_UP
                })
            }
            GhostButton("Export", PyIcons.Download, onClick = actions.export)
            GhostButton("Import", PyIcons.FileUpload, onClick = { dialog = AccountDialog.IMPORT })
        }
    }

    when (dialog) {
        AccountDialog.SIGN_IN -> SignInDialog(
            account = account,
            onSubmit = actions.signIn,
            onSwitch = {
                actions.clearError()
                dialog = AccountDialog.SIGN_UP
            },
            onDismiss = { dialog = AccountDialog.NONE },
        )

        AccountDialog.SIGN_UP -> SignUpDialog(
            account = account,
            onCheckName = actions.checkName,
            onSubmit = actions.signUp,
            onSwitch = {
                actions.clearError()
                dialog = AccountDialog.SIGN_IN
            },
            onDismiss = { dialog = AccountDialog.NONE },
        )

        AccountDialog.MANAGE -> ManageDialog(
            account = account,
            actions = actions,
            onDismiss = { dialog = AccountDialog.NONE },
        )

        AccountDialog.IMPORT -> ImportDialog(
            onPick = { mode ->
                dialog = AccountDialog.NONE
                actions.import(mode)
            },
            onDismiss = { dialog = AccountDialog.NONE },
        )

        AccountDialog.NONE -> Unit
    }
}

@Composable
private fun PasswordField(
    value: String,
    onChange: (String) -> Unit,
    label: String,
    supporting: String = "",
    supportingIsError: Boolean = false,
    imeAction: ImeAction = ImeAction.Next,
) {
    var shown by remember { mutableStateOf(false) }
    OutlinedTextField(
        value = value,
        onValueChange = { if (it.length <= 128) onChange(it) },
        label = { Text(label) },
        singleLine = true,
        visualTransformation = if (shown) VisualTransformation.None else PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password,
            autoCorrectEnabled = false,
            imeAction = imeAction,
        ),
        trailingIcon = {
            TextButton(onClick = { shown = !shown }) { Text(if (shown) "Hide" else "Show") }
        },
        supportingText = if (supporting.isEmpty()) null else {
            {
                Text(
                    supporting,
                    color = if (supportingIsError) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
        },
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun UsernameField(
    value: String,
    onChange: (String) -> Unit,
    supporting: @Composable (() -> Unit)? = null,
) {
    OutlinedTextField(
        value = value,
        onValueChange = { if (it.length <= 24) onChange(it.trim()) },
        label = { Text("Username") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            capitalization = KeyboardCapitalization.None,
            autoCorrectEnabled = false,
            keyboardType = KeyboardType.Ascii,
            imeAction = ImeAction.Next,
        ),
        supportingText = supporting,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun FormError(text: String) {
    if (text.isEmpty()) return
    Spacer(Modifier.height(8.dp))
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.error,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.error.copy(alpha = 0.10f))
            .padding(10.dp),
    )
}

@Composable
private fun SignInDialog(
    account: TeachAccount,
    onSubmit: (String, String) -> Unit,
    onSwitch: () -> Unit,
    onDismiss: () -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!account.busy) onDismiss() },
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(18.dp),
        title = { Text("Sign in to PyCmd", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                UsernameField(name, { name = it })
                Spacer(Modifier.height(6.dp))
                PasswordField(password, { password = it }, "Password", imeAction = ImeAction.Done)
                FormError(account.formError)
                Spacer(Modifier.height(4.dp))
                TextButton(onClick = onSwitch, enabled = !account.busy) {
                    Text("No account? Create one")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSubmit(name, password) },
                enabled = !account.busy && name.isNotBlank() && password.isNotEmpty(),
            ) { Text(if (account.busy) "Signing in…" else "Sign in") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !account.busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun SignUpDialog(
    account: TeachAccount,
    onCheckName: (String) -> Unit,
    onSubmit: (String, String) -> Unit,
    onSwitch: () -> Unit,
    onDismiss: () -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var again by remember { mutableStateOf("") }
    // Asked a moment after typing stops, not on every letter.
    LaunchedEffect(name) {
        if (name.length >= 3) {
            delay(400)
            onCheckName(name)
        }
    }
    val check = account.nameCheck?.takeIf { it.name == name }
    val short = password.isNotEmpty() && password.length < 8
    val mismatch = again.isNotEmpty() && again != password
    AlertDialog(
        onDismissRequest = { if (!account.busy) onDismiss() },
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(18.dp),
        title = { Text("Create a PyCmd account", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                UsernameField(name, { name = it }) {
                    Text(
                        when {
                            name.isEmpty() -> "3 to 24 letters, digits, _ . -"
                            name.length < 3 -> "At least 3 characters"
                            check == null -> "Checking…"
                            check.available -> "✓ $name is free"
                            else -> "✗ ${check.reason}"
                        },
                        color = when {
                            check?.available == true -> MaterialTheme.colorScheme.primary
                            check?.available == false -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
                Spacer(Modifier.height(4.dp))
                PasswordField(
                    password, { password = it }, "Password",
                    supporting = if (short) {
                        "${8 - password.length} more character${if (8 - password.length == 1) "" else "s"}"
                    } else {
                        "Long beats clever: a few words you will remember work well."
                    },
                    supportingIsError = short,
                )
                Spacer(Modifier.height(4.dp))
                PasswordField(
                    again, { again = it }, "Password again",
                    supporting = if (mismatch) "The two passwords are not the same." else "",
                    supportingIsError = mismatch,
                    imeAction = ImeAction.Done,
                )
                FormError(account.formError)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Your password never leaves this phone: PyCmd sends pycmd.pages.dev a key " +
                        "made from it, which cannot be turned back into the password.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TextButton(onClick = onSwitch, enabled = !account.busy) {
                    Text("Have an account? Sign in")
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSubmit(name, password) },
                enabled = !account.busy && name.length >= 3 && password.length >= 8 &&
                    again == password && check?.available != false,
            ) { Text(if (account.busy) "Creating…" else "Create account") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !account.busy) { Text("Cancel") }
        },
    )
}

@Composable
private fun ManageDialog(account: TeachAccount, actions: AccountActions, onDismiss: () -> Unit) {
    var old by remember { mutableStateOf("") }
    var new by remember { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!account.busy) onDismiss() },
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(18.dp),
        title = { Text("Account · ${account.username}", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(
                    "Progress ${syncedText(account.syncedAt)}.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                GhostButton("Sign out of this phone", PyIcons.ArrowBack, onClick = actions.signOut)
                Spacer(Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                Spacer(Modifier.height(12.dp))
                Text("Change password", style = MaterialTheme.typography.titleSmall)
                PasswordField(old, { old = it }, "Current password")
                PasswordField(new, { new = it }, "New password, at least 8 characters",
                    imeAction = ImeAction.Done)
                Text(
                    "Your other devices are signed out and sign in again with the new password.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(6.dp))
                GhostButton(
                    if (account.busy) "Working…" else "Change password",
                    PyIcons.Edit,
                    onClick = { actions.changePassword(old, new) },
                    enabled = !account.busy && old.isNotEmpty() && new.length >= 8,
                )
                Spacer(Modifier.height(14.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                Spacer(Modifier.height(12.dp))
                Text("Delete account", style = MaterialTheme.typography.titleSmall)
                Text(
                    "Removes the account and its saved progress from pycmd.pages.dev. The " +
                        "lessons on this phone stay. This cannot be undone.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                PasswordField(confirmDelete, { confirmDelete = it }, "Password, to confirm",
                    imeAction = ImeAction.Done)
                GhostButton(
                    "Delete my account",
                    PyIcons.Delete,
                    onClick = { actions.delete(confirmDelete) },
                    enabled = !account.busy && confirmDelete.isNotEmpty(),
                    destructive = true,
                )
                FormError(account.formError)
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss, enabled = !account.busy) { Text("Done") }
        },
    )
}

@Composable
private fun ImportDialog(onPick: (String) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(18.dp),
        title = { Text("Import progress", style = MaterialTheme.typography.titleMedium) },
        text = {
            Column {
                Text(
                    "Pick a .json file exported from PyCmd on Android or Windows.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                ImportChoice(
                    "Add to my progress",
                    "Lessons in the file are added. Nothing here is lost.",
                ) { onPick("merge") }
                Spacer(Modifier.height(8.dp))
                ImportChoice(
                    "Replace my progress",
                    "This phone ends up with exactly what is in the file. If you are " +
                        "signed in, your other devices follow at their next sync.",
                    destructive = true,
                ) { onPick("replace") }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun ImportChoice(
    title: String,
    detail: String,
    destructive: Boolean = false,
    onClick: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .border(
                1.dp,
                if (destructive) {
                    MaterialTheme.colorScheme.error.copy(alpha = 0.5f)
                } else {
                    MaterialTheme.colorScheme.outline
                },
                RoundedCornerShape(12.dp),
            )
            .clickable(onClick = onClick)
            .padding(12.dp),
    ) {
        Text(title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        Text(
            detail,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
