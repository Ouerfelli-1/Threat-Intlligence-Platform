'use client';

import React, { useCallback, useState } from 'react';
import useSWR from 'swr';
import FilterBar from '@/components/shared/FilterBar';
import { Upload, Plus, More, Refresh, X, AlertTriangle, Check, Trash } from '@/components/icons';
import { useUsers, Role } from '@/lib/hooks';
import { api, fetcher } from '@/lib/api';

function roleBg(r: string) {
  if (r === 'admin')     return 'rgba(248,81,73,0.12)';
  if (r === 'service')   return 'rgba(88,166,255,0.12)';
  if (r === 'read-only' || r === 'viewer') return 'var(--bg-elev)';
  return 'rgba(88,166,255,0.08)';
}

function fmtDate(iso: string | null): string {
  if (!iso) return 'never';
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

interface UserForm {
  username: string;
  password: string;
  role_id: string;
  active: boolean;
}

export default function UsersPage() {
  const { items: users, total, isLoading, mutate } = useUsers();
  const { data: roles = [] } = useSWR<Role[]>('/roles', fetcher);

  // Filters
  const [filter, setFilter]   = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all');

  // Add modal
  const [showAdd, setShowAdd]       = useState(false);
  const [creating, setCreating]     = useState(false);
  const [addError, setAddError]     = useState<string | null>(null);
  const [form, setForm] = useState<UserForm>({ username: '', password: '', role_id: '', active: true });

  // Edit modal
  const [editing, setEditing]       = useState<{ id: string; username: string; role_id: string; active: boolean } | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError]   = useState<string | null>(null);
  const [editForm, setEditForm]     = useState({ role_id: '', active: true, password: '' });

  const openAdd = useCallback(() => {
    setAddError(null);
    setForm({
      username: '',
      password: '',
      role_id: roles[0]?.id ?? '',
      active: true,
    });
    setShowAdd(true);
  }, [roles]);

  const submitAdd = useCallback(async () => {
    if (!form.username.trim() || !form.password) { setAddError('Username and password are required'); return; }
    if (!form.role_id) { setAddError('Pick a role'); return; }
    if (form.password.length < 8) { setAddError('Password must be at least 8 characters'); return; }
    setCreating(true); setAddError(null);
    try {
      await api.post('/users', {
        username: form.username.trim(),
        password: form.password,
        role_id: form.role_id,
        active: form.active,
        supplementary_permissions: [],
      });
      setShowAdd(false);
      mutate();
    } catch (e) { setAddError(String(e)); }
    finally { setCreating(false); }
  }, [form, mutate]);

  const openEdit = useCallback((u: { id: string; username: string; role: string; role_id?: string; active: boolean }) => {
    setEditError(null);
    setEditing({ id: u.id, username: u.username, role_id: u.role_id ?? '', active: u.active });
    setEditForm({ role_id: u.role_id ?? '', active: u.active, password: '' });
  }, []);

  const submitEdit = useCallback(async () => {
    if (!editing) return;
    setSavingEdit(true); setEditError(null);
    try {
      const body: Record<string, unknown> = {
        role_id: editForm.role_id,
        active: editForm.active,
      };
      if (editForm.password) {
        if (editForm.password.length < 8) { setEditError('New password must be at least 8 characters'); setSavingEdit(false); return; }
        body.password = editForm.password;
      }
      await api.patch(`/users/${editing.id}`, body);
      setEditing(null);
      mutate();
    } catch (e) { setEditError(String(e)); }
    finally { setSavingEdit(false); }
  }, [editing, editForm, mutate]);

  const deleteUser = useCallback(async (id: string, username: string) => {
    if (!confirm(`Delete user "${username}"? Their sessions will be invalidated.`)) return;
    try { await api.delete(`/users/${id}`); mutate(); }
    catch (e) { alert(String(e)); }
  }, [mutate]);

  // Apply local filters
  const filtered = users.filter((u) => {
    if (filter && !u.username.toLowerCase().includes(filter.toLowerCase()) && !(u.email ?? '').toLowerCase().includes(filter.toLowerCase()) && !u.role.toLowerCase().includes(filter.toLowerCase())) return false;
    if (roleFilter && u.role !== roleFilter) return false;
    if (activeFilter === 'active' && !u.active) return false;
    if (activeFilter === 'inactive' && u.active) return false;
    return true;
  });

  const active = users.filter((u) => u.active).length;
  const services = users.filter((u) => u.role === 'service').length;

  return (
    <div style={{ padding: 14, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Users</div>
        <div style={{ color: 'var(--text-4)', fontSize: 12, marginLeft: 10 }}>
          {isLoading ? 'loading…' : `${active} active · ${services} service accounts · ${total} total`}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => mutate()}><Refresh s={12} />Refresh</button>
          <button className="btn" disabled title="SCIM import not implemented yet"><Upload s={12} />SCIM import</button>
          <button className="btn primary" onClick={openAdd}><Plus s={12} />Add user</button>
        </div>
      </div>

      <FilterBar search="Username, email, role…" value={filter} onSearch={setFilter}>
        <select className="select" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="">All roles</option>
          {roles.map((r) => <option key={r.id} value={r.name}>{r.name}</option>)}
        </select>
        <select className="select" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as 'all' | 'active' | 'inactive')}>
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </FilterBar>

      <div className="card" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
        <table className="tbl">
          <thead><tr>
            <th style={{ width: 30 }}><input type="checkbox" /></th>
            <th style={{ width: 220 }}>Username</th>
            <th>Email</th>
            <th style={{ width: 130 }}>Role</th>
            <th style={{ width: 80 }}>Active</th>
            <th style={{ width: 180 }}>Last login</th>
            <th style={{ width: 130 }}>Actions</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>Loading users…</td></tr>}
            {!isLoading && filtered.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', padding: 30, color: 'var(--text-4)' }}>No users match.</td></tr>}
            {filtered.map((u) => (
              <tr key={u.id}>
                <td><input type="checkbox" /></td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'linear-gradient(135deg,#2dd4bf,#a371f7)', display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 600, color: '#0a1a18' }}>
                      {u.username.split('.').map((s) => s[0]).join('').slice(0, 2).toUpperCase()}
                    </div>
                    <span className="mono" style={{ fontSize: 11.5, color: 'var(--text)' }}>{u.username}</span>
                  </div>
                </td>
                <td className="mono" style={{ fontSize: 11 }}>{u.email ?? '—'}</td>
                <td><span className="tag" style={{ background: roleBg(u.role) }}>{u.role}</span></td>
                <td>{u.active ? <span className="badge low"><span className="dot pulse" />active</span> : <span className="badge mute">disabled</span>}</td>
                <td className="mono" style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtDate(u.last_login_at)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn sm" style={{ padding: '2px 8px', fontSize: 10 }} onClick={() => openEdit(u as { id: string; username: string; role: string; role_id?: string; active: boolean })}>Edit</button>
                    <button className="btn sm" style={{ padding: '2px 6px' }} onClick={() => deleteUser(u.id, u.username)} title="Delete user">
                      <Trash s={11} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Add user modal */}
      {showAdd && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 480, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Plus s={14} /><div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Add user</div>
              <button className="btn sm" onClick={() => setShowAdd(false)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Username *</label>
                <input className="input mono" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                  placeholder="e.g. yassine.bouazza" style={{ width: '100%', fontSize: 12 }} autoFocus />
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Password *</label>
                <input className="input mono" type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="minimum 8 characters" style={{ width: '100%', fontSize: 12 }} />
                <div style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 2 }}>
                  The user should rotate this on first login. Argon2id is used at rest.
                </div>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Role *</label>
                <select className="select" value={form.role_id} onChange={(e) => setForm((f) => ({ ...f, role_id: e.target.value }))} style={{ width: '100%' }}>
                  <option value="">Select role…</option>
                  {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)', cursor: 'pointer' }}>
                <input type="checkbox" checked={form.active} onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))} />
                Active — user can log in immediately
              </label>
              {addError && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
                  <AlertTriangle s={11} style={{ marginRight: 4 }} />{addError}
                </div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setShowAdd(false)}>Cancel</button>
              <button className="btn primary" onClick={submitAdd} disabled={creating}>
                {creating ? <><Refresh s={11} />Creating…</> : <><Plus s={11} />Create user</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit user modal */}
      {editing && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(1,4,9,0.7)', backdropFilter: 'blur(4px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ width: 480, maxHeight: '90vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-card)', border: '1px solid var(--border-strong)', borderRadius: 12, boxShadow: '0 16px 48px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Check s={14} /><div style={{ fontSize: 14, fontWeight: 600, flex: 1 }}>Edit user: <span className="mono">{editing.username}</span></div>
              <button className="btn sm" onClick={() => setEditing(null)}><X s={12} /></button>
            </div>
            <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1 }}>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Role</label>
                <select className="select" value={editForm.role_id} onChange={(e) => setEditForm((f) => ({ ...f, role_id: e.target.value }))} style={{ width: '100%' }}>
                  {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 4 }}>Reset password (optional)</label>
                <input className="input mono" type="password" value={editForm.password} onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  placeholder="leave blank to keep current" style={{ width: '100%', fontSize: 12 }} />
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)', cursor: 'pointer' }}>
                <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm((f) => ({ ...f, active: e.target.checked }))} />
                Active
              </label>
              {editError && (
                <div style={{ padding: '8px 10px', background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 6, color: '#f85149', fontSize: 11.5 }}>
                  <AlertTriangle s={11} style={{ marginRight: 4 }} />{editError}
                </div>
              )}
            </div>
            <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn primary" onClick={submitEdit} disabled={savingEdit}>
                {savingEdit ? <><Refresh s={11} />Saving…</> : <><Check s={11} />Save</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
