'use client';

import React, { ReactNode, useState, useCallback } from 'react';
import Flag from '@/components/shared/Flag';
import {
  Building, Server, Globe, Shield, Radar, AlertTriangle,
  Settings, Clock, Activity, Refresh, Check, X, Plus,
} from '@/components/icons';
import { useProfile } from '@/lib/hooks';
import type {
  Profile, ProfileIdentity, ProfileTechnology, ProfileExposure,
  ProfileCompliance, ProfileGeopolitical, ProfileRisk,
} from '@/lib/hooks';
import { api } from '@/lib/api';

/* ---------- Tag input component ---------- */
function TagInput({ value, onChange, placeholder }: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState('');

  function addTag(raw: string) {
    const tags = raw.split(/[,\n]+/).map(s => s.trim()).filter(Boolean);
    if (tags.length === 0) return;
    onChange([...new Set([...value, ...tags])]);
    setDraft('');
  }
  function removeTag(idx: number) { onChange(value.filter((_, i) => i !== idx)); }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: '6px 8px', minHeight: 36, background: 'var(--bg-page)', display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
      {value.map((t, i) => (
        <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(88,166,255,0.12)', border: '1px solid rgba(88,166,255,0.25)', borderRadius: 4, padding: '2px 6px', fontSize: 11.5, color: 'var(--text-2)' }}>
          {t}
          <button onClick={() => removeTag(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--text-4)', lineHeight: 1 }}>×</button>
        </span>
      ))}
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(draft); }
          if (e.key === 'Backspace' && !draft && value.length > 0) removeTag(value.length - 1);
        }}
        onBlur={() => draft && addTag(draft)}
        placeholder={value.length === 0 ? (placeholder ?? 'Type and press Enter…') : ''}
        style={{ flex: 1, minWidth: 80, background: 'none', border: 'none', outline: 'none', fontSize: 12, color: 'var(--text)', padding: '1px 0' }}
      />
    </div>
  );
}

/* ---------- Toggle ---------- */
function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div onClick={() => onChange(!value)} style={{ width: 36, height: 20, borderRadius: 10, background: value ? 'var(--accent)' : 'var(--border)', transition: 'background 0.2s', position: 'relative', cursor: 'pointer', flexShrink: 0 }}>
      <div style={{ width: 14, height: 14, borderRadius: 7, background: '#fff', position: 'absolute', top: 3, left: value ? 18 : 3, transition: 'left 0.2s' }} />
    </div>
  );
}

/* ---------- Field ---------- */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 11.5, color: 'var(--text-4)', display: 'block', marginBottom: 5 }}>{label}</label>
      {children}
    </div>
  );
}
function TextInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input
      value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
      style={{ width: '100%', background: 'var(--bg-page)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', fontSize: 13, color: 'var(--text)', boxSizing: 'border-box' }}
    />
  );
}

/* ---------- Edit modal ---------- */
type SectionId = 'identity' | 'technology' | 'exposure' | 'compliance' | 'geopolitical' | 'risk';

const SECTION_LABELS: Record<SectionId, string> = {
  identity: 'Identity', technology: 'Technology Stack',
  exposure: 'External Exposure', compliance: 'Compliance & Policy',
  geopolitical: 'Geopolitical Exposure', risk: 'Risk & Crown Jewels',
};

function EditModal({ section, profile, onSave, onClose }: {
  section: SectionId;
  profile: Profile | undefined;
  onSave: (section: SectionId, data: unknown) => Promise<void>;
  onClose: () => void;
}) {
  const emptyIdentity: ProfileIdentity = { name: '', sector: '', hq_country: '', countries_of_operation: [], public_domains: [], public_ip_ranges: [], asn_numbers: [], language: 'en' };
  const emptyTech: ProfileTechnology = { operating_systems: [], endpoint_os: [], software: [], network_devices: [], cloud_providers: [], identity_providers: [], remote_access: [], security_tools: [], industrial_ot: false };
  const emptyExposure: ProfileExposure = { internet_facing_services: [], mobile_workforce: false, third_party_access: false, supply_chain_vendors: [], critical_data_types: [] };
  const emptyCompliance: ProfileCompliance = { regulatory_frameworks: [], certifications: [], data_residency_requirements: [] };
  const emptyGeo: ProfileGeopolitical = { geopolitical_regions: [], conflict_adjacent: false, notable_partnerships: [], sanctions_exposure: false };
  const emptyRisk: ProfileRisk = { risk_appetite: 'medium', crown_jewels: [], previous_incidents: [], threat_concerns: [] };

  const [identity, setIdentity] = useState<ProfileIdentity>(profile?.identity ?? emptyIdentity);
  const [tech, setTech] = useState<ProfileTechnology>(profile?.technology ?? emptyTech);
  const [exposure, setExposure] = useState<ProfileExposure>(profile?.exposure ?? emptyExposure);
  const [compliance, setCompliance] = useState<ProfileCompliance>(profile?.compliance ?? emptyCompliance);
  const [geo, setGeo] = useState<ProfileGeopolitical>(profile?.geopolitical ?? emptyGeo);
  const [risk, setRisk] = useState<ProfileRisk>(profile?.risk ?? emptyRisk);

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  function getData(): unknown {
    switch (section) {
      case 'identity':    return identity;
      case 'technology':  return tech;
      case 'exposure':    return exposure;
      case 'compliance':  return compliance;
      case 'geopolitical':return geo;
      case 'risk':        return risk;
    }
  }

  async function handleSave() {
    // Validate identity required fields
    if (section === 'identity') {
      if (!identity.name.trim())       { setErr('Organization name is required'); return; }
      if (!identity.sector.trim())     { setErr('Sector is required'); return; }
      if (!identity.hq_country.trim()) { setErr('HQ country is required'); return; }
    }
    setSaving(true); setErr('');
    try {
      await onSave(section, getData());
      onClose();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Save failed. Check required fields.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{ width: 580, maxHeight: '90vh', background: 'var(--bg-page)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 24px 64px rgba(0,0,0,0.5)' }}>
        {/* Header */}
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Settings s={14} />
          <div style={{ fontWeight: 600, fontSize: 14 }}>Edit — {SECTION_LABELS[section]}</div>
          <button className="btn sm" onClick={onClose} style={{ marginLeft: 'auto' }}><X s={11} />Cancel</button>
        </div>

        {/* Form */}
        <div style={{ flex: 1, overflow: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>

          {section === 'identity' && <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Field label="Organization name *"><TextInput value={identity.name} onChange={v => setIdentity(p => ({ ...p, name: v }))} placeholder="Acme Bank" /></Field>
              <Field label="Sector *"><TextInput value={identity.sector} onChange={v => setIdentity(p => ({ ...p, sector: v }))} placeholder="finance" /></Field>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Field label="HQ country (ISO-2) *"><TextInput value={identity.hq_country} onChange={v => setIdentity(p => ({ ...p, hq_country: v.toUpperCase().slice(0, 2) }))} placeholder="MA" /></Field>
              <Field label="Employee count range"><TextInput value={identity.employee_count_range ?? ''} onChange={v => setIdentity(p => ({ ...p, employee_count_range: v }))} placeholder="500-1000" /></Field>
            </div>
            <Field label="Countries of operation (ISO-2 codes)">
              <TagInput value={identity.countries_of_operation} onChange={v => setIdentity(p => ({ ...p, countries_of_operation: v }))} placeholder="MA, FR, SN" />
            </Field>
            <Field label="Public domains">
              <TagInput value={identity.public_domains} onChange={v => setIdentity(p => ({ ...p, public_domains: v }))} placeholder="example.com, api.example.com" />
            </Field>
            <Field label="Public IP ranges (CIDR or single IPs)">
              <TagInput value={identity.public_ip_ranges} onChange={v => setIdentity(p => ({ ...p, public_ip_ranges: v }))} placeholder="196.0.0.0/24, 1.2.3.4" />
            </Field>
            <Field label="ASN numbers">
              <TagInput value={identity.asn_numbers} onChange={v => setIdentity(p => ({ ...p, asn_numbers: v }))} placeholder="AS37705" />
            </Field>
          </>}

          {section === 'technology' && <>
            <Field label="Software (ERP, CRM, core banking…)"><TagInput value={tech.software} onChange={v => setTech(p => ({ ...p, software: v }))} placeholder="SAP, T24, Salesforce" /></Field>
            <Field label="Operating systems"><TagInput value={tech.operating_systems} onChange={v => setTech(p => ({ ...p, operating_systems: v }))} placeholder="Windows Server 2019, Ubuntu 22.04" /></Field>
            <Field label="Cloud providers"><TagInput value={tech.cloud_providers} onChange={v => setTech(p => ({ ...p, cloud_providers: v }))} placeholder="AWS, Azure, GCP" /></Field>
            <Field label="Network devices / vendors"><TagInput value={tech.network_devices} onChange={v => setTech(p => ({ ...p, network_devices: v }))} placeholder="Cisco, Palo Alto, Fortinet" /></Field>
            <Field label="Security tools"><TagInput value={tech.security_tools} onChange={v => setTech(p => ({ ...p, security_tools: v }))} placeholder="Wazuh, Splunk, CrowdStrike" /></Field>
            <Field label="Identity providers (IAM / SSO)"><TagInput value={tech.identity_providers} onChange={v => setTech(p => ({ ...p, identity_providers: v }))} placeholder="Microsoft AD, Okta" /></Field>
            <Field label="Remote access tools"><TagInput value={tech.remote_access} onChange={v => setTech(p => ({ ...p, remote_access: v }))} placeholder="VPN, Citrix, Zscaler" /></Field>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <Toggle value={tech.industrial_ot} onChange={v => setTech(p => ({ ...p, industrial_ot: v }))} />
              <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>Industrial / OT systems present</span>
            </label>
          </>}

          {section === 'exposure' && <>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <Toggle value={exposure.mobile_workforce} onChange={v => setExposure(p => ({ ...p, mobile_workforce: v }))} />
              <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>Mobile / remote workforce</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <Toggle value={exposure.third_party_access} onChange={v => setExposure(p => ({ ...p, third_party_access: v }))} />
              <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>Third-party / vendor access to systems</span>
            </label>
            <Field label="Internet-facing services"><TagInput value={exposure.internet_facing_services} onChange={v => setExposure(p => ({ ...p, internet_facing_services: v }))} placeholder="Customer portal, API gateway, VPN" /></Field>
            <Field label="Supply-chain vendors (critical)"><TagInput value={exposure.supply_chain_vendors} onChange={v => setExposure(p => ({ ...p, supply_chain_vendors: v }))} placeholder="Temenos, Oracle, SWIFT" /></Field>
            <Field label="Critical data types"><TagInput value={exposure.critical_data_types} onChange={v => setExposure(p => ({ ...p, critical_data_types: v }))} placeholder="PII, financial records, card data" /></Field>
          </>}

          {section === 'compliance' && <>
            <Field label="Regulatory frameworks"><TagInput value={compliance.regulatory_frameworks} onChange={v => setCompliance(p => ({ ...p, regulatory_frameworks: v }))} placeholder="ISO 27001, PCI-DSS, GDPR, SOC 2" /></Field>
            <Field label="Certifications"><TagInput value={compliance.certifications} onChange={v => setCompliance(p => ({ ...p, certifications: v }))} placeholder="ISO 27001:2022 certified" /></Field>
            <Field label="Data residency requirements"><TagInput value={compliance.data_residency_requirements} onChange={v => setCompliance(p => ({ ...p, data_residency_requirements: v }))} placeholder="Data must remain in Morocco" /></Field>
          </>}

          {section === 'geopolitical' && <>
            <Field label="Geopolitical regions"><TagInput value={geo.geopolitical_regions} onChange={v => setGeo(p => ({ ...p, geopolitical_regions: v }))} placeholder="North Africa, MENA, Sub-Saharan Africa" /></Field>
            <Field label="Notable partnerships / alliances"><TagInput value={geo.notable_partnerships} onChange={v => setGeo(p => ({ ...p, notable_partnerships: v }))} placeholder="IMF, World Bank" /></Field>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <Toggle value={geo.conflict_adjacent} onChange={v => setGeo(p => ({ ...p, conflict_adjacent: v }))} />
              <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>Conflict-adjacent region</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <Toggle value={geo.sanctions_exposure} onChange={v => setGeo(p => ({ ...p, sanctions_exposure: v }))} />
              <span style={{ fontSize: 12.5, color: 'var(--text-2)' }}>Sanctions exposure risk</span>
            </label>
          </>}

          {section === 'risk' && <>
            <Field label="Risk appetite">
              <div style={{ display: 'flex', gap: 8 }}>
                {(['low', 'medium', 'high'] as const).map(opt => (
                  <button key={opt} onClick={() => setRisk(p => ({ ...p, risk_appetite: opt }))}
                    style={{ flex: 1, padding: '8px 12px', borderRadius: 6, fontSize: 12.5, fontWeight: 500, cursor: 'pointer', border: `1px solid ${risk.risk_appetite === opt ? 'var(--accent)' : 'var(--border)'}`, background: risk.risk_appetite === opt ? 'rgba(88,166,255,0.12)' : 'var(--bg-page)', color: risk.risk_appetite === opt ? 'var(--accent)' : 'var(--text-4)', textTransform: 'capitalize' }}>
                    {opt === 'low' ? '🟢' : opt === 'medium' ? '🟡' : '🔴'} {opt}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Crown jewels (critical assets)"><TagInput value={risk.crown_jewels} onChange={v => setRisk(p => ({ ...p, crown_jewels: v }))} placeholder="Customer database, SWIFT system, Core banking" /></Field>
            <Field label="Threat concerns"><TagInput value={risk.threat_concerns} onChange={v => setRisk(p => ({ ...p, threat_concerns: v }))} placeholder="ransomware, data exfiltration, supply chain" /></Field>
            <Field label="Previous incidents"><TagInput value={risk.previous_incidents} onChange={v => setRisk(p => ({ ...p, previous_incidents: v }))} placeholder="Phishing 2023, Credential theft 2024" /></Field>
          </>}

        </div>

        {err && (
          <div style={{ padding: '8px 18px', background: 'rgba(248,81,73,0.08)', borderTop: '1px solid rgba(248,81,73,0.2)', fontSize: 12, color: '#f85149' }}>{err}</div>
        )}
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn" onClick={onClose} disabled={saving}><X s={11} />Cancel</button>
          <button className="btn primary" onClick={handleSave} disabled={saving}>
            <Check s={11} />{saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Display helpers ---------- */
function Sec({ icon: Ic, title, sub, onEdit, children }: {
  icon: React.FC<{ s?: number }>;
  title: string;
  sub: string;
  onEdit: () => void;
  children: ReactNode;
}) {
  return (
    <div className="card">
      <div className="card-h">
        <Ic s={13} /><div className="t">{title}</div><div className="s">{sub}</div>
        <div className="right"><button className="btn sm" onClick={onEdit}><Settings s={11} />Edit</button></div>
      </div>
      <div className="card-b">{children}</div>
    </div>
  );
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border-soft)' }}>
      <div style={{ fontSize: 11.5, color: 'var(--text-4)' }}>{k}</div>
      <div style={{ fontSize: 12.5, color: 'var(--text-2)' }}>{children}</div>
    </div>
  );
}

function Tags({ items }: { items: string[] }) {
  if (!items?.length) return <span style={{ color: 'var(--text-4)', fontSize: 11 }}>—</span>;
  return <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{items.map(t => <span key={t} className="tag">{t}</span>)}</div>;
}

function fmtDate(iso: string | null | undefined) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ---------- Page ---------- */
export default function ProfilePage() {
  const { data: profile, isLoading, mutate } = useProfile();
  const [editSection, setEditSection] = useState<SectionId | null>(null);
  const [saveMsg, setSaveMsg] = useState('');

  const handleSave = useCallback(async (section: SectionId, data: unknown) => {
    await api.patch('/profile', { [section]: data });
    await mutate();
    setSaveMsg('Profile updated ✓');
    setTimeout(() => setSaveMsg(''), 3000);
  }, [mutate]);

  if (isLoading) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-4)' }}>Loading company profile…</div>;
  }

  const identity    = profile?.identity    ?? {} as Partial<ProfileIdentity>;
  const technology  = profile?.technology  ?? {} as Partial<ProfileTechnology>;
  const geopolitical= profile?.geopolitical?? {} as Partial<ProfileGeopolitical>;
  const compliance  = profile?.compliance  ?? {} as Partial<ProfileCompliance>;
  const exposure    = profile?.exposure    ?? {} as Partial<ProfileExposure>;
  const risk        = profile?.risk        ?? {} as Partial<ProfileRisk>;

  return (
    <div style={{ padding: 14, height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 12, gap: 12 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Company Profile</div>
          <div style={{ color: 'var(--text-4)', fontSize: 12 }}>
            {profile
              ? `last edited ${fmtDate(profile.edited_at)}`
              : 'No profile yet — click Edit on any section to create one'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Refresh + Versions + Change-log buttons removed — Refresh was a
              no-op for users (SWR auto-revalidates on mount) and Versions /
              Change-log were stubs with no UI behind them. The save-confirmation
              chip is enough feedback that the profile is current. */}
          {saveMsg && <span style={{ fontSize: 12, color: '#3fb950', display: 'flex', alignItems: 'center', gap: 4 }}><Check s={12} />{saveMsg}</span>}
        </div>
      </div>

      {!profile && (
        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-4)' }}>
          <Building s={36} />
          <div style={{ marginTop: 12, fontSize: 13 }}>No company profile has been configured.</div>
          <div style={{ marginTop: 6, fontSize: 12 }}>Start with the Identity section — it&apos;s required for the AI relevance scoring to work.</div>
          <button className="btn primary" style={{ marginTop: 16 }} onClick={() => setEditSection('identity')}>
            <Plus s={12} />Create profile — start with Identity
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        {/* Identity */}
        <Sec icon={Building} title="Identity" sub="who we are" onEdit={() => setEditSection('identity')}>
          <Row k="Name">{(identity as ProfileIdentity).name ?? '—'}</Row>
          <Row k="Sector">{(identity as ProfileIdentity).sector ?? '—'}</Row>
          <Row k="HQ">
            {(identity as ProfileIdentity).hq_country
              ? <><Flag code={(identity as ProfileIdentity).hq_country} /> {(identity as ProfileIdentity).hq_country}</>
              : '—'}
          </Row>
          <Row k="Countries">
            {((identity as ProfileIdentity).countries_of_operation ?? []).length > 0
              ? <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {((identity as ProfileIdentity).countries_of_operation).map(c => (
                    <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 3 }}><Flag code={c} />{c}</span>
                  ))}
                </div>
              : '—'}
          </Row>
          <Row k="Size">{(identity as ProfileIdentity).employee_count_range ?? '—'}</Row>
          <Row k="Domains"><Tags items={(identity as ProfileIdentity).public_domains ?? []} /></Row>
          <Row k="IP ranges"><Tags items={(identity as ProfileIdentity).public_ip_ranges ?? []} /></Row>
          <Row k="ASNs">
            {((identity as ProfileIdentity).asn_numbers ?? []).length > 0
              ? <span className="mono">{(identity as ProfileIdentity).asn_numbers.join(' · ')}</span>
              : '—'}
          </Row>
        </Sec>

        {/* Technology */}
        <Sec icon={Server} title="Technology" sub="stack inventory" onEdit={() => setEditSection('technology')}>
          {(technology as ProfileTechnology).software?.length > 0   && <Row k="Software"><Tags items={(technology as ProfileTechnology).software} /></Row>}
          {(technology as ProfileTechnology).operating_systems?.length > 0 && <Row k="OS"><Tags items={(technology as ProfileTechnology).operating_systems} /></Row>}
          {(technology as ProfileTechnology).network_devices?.length > 0   && <Row k="Network"><Tags items={(technology as ProfileTechnology).network_devices} /></Row>}
          {(technology as ProfileTechnology).cloud_providers?.length > 0   && <Row k="Cloud"><Tags items={(technology as ProfileTechnology).cloud_providers} /></Row>}
          {(technology as ProfileTechnology).security_tools?.length > 0    && <Row k="Security tools"><Tags items={(technology as ProfileTechnology).security_tools} /></Row>}
          {(technology as ProfileTechnology).identity_providers?.length > 0&& <Row k="IAM / SSO"><Tags items={(technology as ProfileTechnology).identity_providers} /></Row>}
          {(technology as ProfileTechnology).industrial_ot && <Row k="OT / ICS"><span className="badge high">Present</span></Row>}
          {!profile?.technology && (
            <div style={{ fontSize: 12, color: 'var(--text-4)', padding: 10 }}>
              No technology stack.{' '}<button className="btn sm" onClick={() => setEditSection('technology')}><Plus s={10} />Add</button>
            </div>
          )}
        </Sec>

        {/* Geopolitical */}
        <Sec icon={Globe} title="Geopolitical" sub="exposure model" onEdit={() => setEditSection('geopolitical')}>
          <Row k="Regions"><Tags items={(geopolitical as ProfileGeopolitical).geopolitical_regions ?? []} /></Row>
          <Row k="Partnerships"><Tags items={(geopolitical as ProfileGeopolitical).notable_partnerships ?? []} /></Row>
          <Row k="Conflict-adjacent">
            {(geopolitical as ProfileGeopolitical).conflict_adjacent != null
              ? <span className={`badge ${(geopolitical as ProfileGeopolitical).conflict_adjacent ? 'high' : 'low'}`}>{(geopolitical as ProfileGeopolitical).conflict_adjacent ? 'Yes' : 'No'}</span>
              : '—'}
          </Row>
          <Row k="Sanctions exposure">
            {(geopolitical as ProfileGeopolitical).sanctions_exposure != null
              ? <span className={`badge ${(geopolitical as ProfileGeopolitical).sanctions_exposure ? 'high' : 'low'}`}>{(geopolitical as ProfileGeopolitical).sanctions_exposure ? 'Exposed' : 'No'}</span>
              : '—'}
          </Row>
        </Sec>

        {/* Compliance */}
        <Sec icon={Shield} title="Compliance &amp; policy" sub="frameworks in scope" onEdit={() => setEditSection('compliance')}>
          {((compliance as ProfileCompliance).regulatory_frameworks ?? []).length > 0 && (
            <Row k="Frameworks"><Tags items={(compliance as ProfileCompliance).regulatory_frameworks} /></Row>
          )}
          {((compliance as ProfileCompliance).certifications ?? []).length > 0 && (
            <Row k="Certifications"><Tags items={(compliance as ProfileCompliance).certifications} /></Row>
          )}
          {((compliance as ProfileCompliance).data_residency_requirements ?? []).length > 0 && (
            <Row k="Data residency"><Tags items={(compliance as ProfileCompliance).data_residency_requirements} /></Row>
          )}
          {!profile?.compliance && (
            <div style={{ fontSize: 12, color: 'var(--text-4)', padding: 10 }}>
              No compliance data.{' '}<button className="btn sm" onClick={() => setEditSection('compliance')}><Plus s={10} />Add</button>
            </div>
          )}
        </Sec>

        {/* Exposure */}
        <Sec icon={Radar} title="Exposure" sub="external attack surface" onEdit={() => setEditSection('exposure')}>
          <Row k="Mobile workforce">
            {(exposure as ProfileExposure).mobile_workforce != null
              ? <span className={`badge ${(exposure as ProfileExposure).mobile_workforce ? 'med' : 'mute'}`}>{(exposure as ProfileExposure).mobile_workforce ? 'Yes' : 'No'}</span>
              : '—'}
          </Row>
          <Row k="Third-party access">
            {(exposure as ProfileExposure).third_party_access != null
              ? <span className={`badge ${(exposure as ProfileExposure).third_party_access ? 'med' : 'mute'}`}>{(exposure as ProfileExposure).third_party_access ? 'Yes' : 'No'}</span>
              : '—'}
          </Row>
          <Row k="Internet-facing"><Tags items={(exposure as ProfileExposure).internet_facing_services ?? []} /></Row>
          <Row k="Supply-chain vendors"><Tags items={(exposure as ProfileExposure).supply_chain_vendors ?? []} /></Row>
          <Row k="Critical data"><Tags items={(exposure as ProfileExposure).critical_data_types ?? []} /></Row>
        </Sec>

        {/* Risk */}
        <Sec icon={AlertTriangle} title="Risk" sub="appetite &amp; concerns" onEdit={() => setEditSection('risk')}>
          {(risk as ProfileRisk).risk_appetite && (
            <Row k="Risk appetite">
              <span className={`badge ${(risk as ProfileRisk).risk_appetite === 'low' ? 'low' : (risk as ProfileRisk).risk_appetite === 'medium' ? 'med' : 'high'}`}>
                {(risk as ProfileRisk).risk_appetite}
              </span>
            </Row>
          )}
          {((risk as ProfileRisk).crown_jewels ?? []).length > 0 && (
            <Row k="Crown jewels"><Tags items={(risk as ProfileRisk).crown_jewels} /></Row>
          )}
          {((risk as ProfileRisk).threat_concerns ?? []).length > 0 && (
            <Row k="Threat concerns"><Tags items={(risk as ProfileRisk).threat_concerns} /></Row>
          )}
          {((risk as ProfileRisk).previous_incidents ?? []).length > 0 && (
            <Row k="Past incidents"><Tags items={(risk as ProfileRisk).previous_incidents} /></Row>
          )}
          {!profile?.risk && (
            <div style={{ fontSize: 12, color: 'var(--text-4)', padding: 10 }}>
              No risk config.{' '}<button className="btn sm" onClick={() => setEditSection('risk')}><Plus s={10} />Add</button>
            </div>
          )}
        </Sec>
      </div>

      {/* Edit modal */}
      {editSection && (
        <EditModal
          section={editSection}
          profile={profile}
          onSave={handleSave}
          onClose={() => setEditSection(null)}
        />
      )}
    </div>
  );
}
