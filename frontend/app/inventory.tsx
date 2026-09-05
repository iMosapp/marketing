import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, TextInput, ScrollView, ActivityIndicator,
  RefreshControl, Modal, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { Image } from 'expo-image';
import { PhotoGallerySheet, pickPhotoBase64 } from '../components/inventory/PhotoGallerySheet';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { resolvePhotoUrl } from '../utils/photoUrl';
import api from '../services/api';
import { showSimpleAlert, showConfirm } from '../services/alert';

const ACCENT = '#32ADE6';

const EMPTY_FORM = { year: '', make: '', model: '', trim: '', body_type: '', color: '', mileage: '', price: '', stock_number: '', vin: '', description: '' };
const BODY_TYPES = ['Truck', 'SUV', 'Sedan', 'Van', 'Coupe', 'Convertible', 'Hatchback', 'Wagon'];

export default function InventoryScreen() {
  const { colors } = useThemeStore();
  const { user, isLoading: authLoading } = useAuthStore();
  const router = useRouter();

  const [items, setItems] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('available');
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [photoUploadingId, setPhotoUploadingId] = useState<string | null>(null);
  const [galleryItem, setGalleryItem] = useState<any | null>(null);

  const handleAddPhoto = async (item: any) => {
    if (!user?._id) return;
    if ((item.photos || []).length > 0) { setGalleryItem(item); return; }
    try {
      const photo = await pickPhotoBase64();
      if (!photo) return;
      setPhotoUploadingId(item._id);
      const r = await api.post(`/inventory/${user._id}/${item._id}/photo`, { photo });
      applyPhotos(item._id, r.data.photos || []);
    } catch {
      showSimpleAlert('Error', 'Could not upload the photo. Please try again.');
    } finally {
      setPhotoUploadingId(null);
    }
  };

  const applyPhotos = (itemId: string, photos: any[]) => {
    const cover = photos[0];
    const patch = { photos, photo_url: cover?.thumb_url || null, photo_full_path: cover?.full_path || null };
    setItems(prev => prev.map(i => (i._id === itemId ? { ...i, ...patch } : i)));
    setGalleryItem((g: any) => (g && g._id === itemId ? { ...g, ...patch } : g));
  };

  const fetchItems = useCallback(async () => {
    if (!user?._id) { setLoading(false); return; }
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (statusFilter !== 'all') params.set('status', statusFilter);
      const res = await api.get(`/inventory/${user._id}?${params.toString()}`);
      setItems(res.data.items || []);
      setCounts(res.data.counts || {});
    } catch (e) {
      console.error('Inventory fetch failed:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, search, statusFilter]);

  useFocusEffect(useCallback(() => {
    if (authLoading) return; // session still hydrating (cold start / web reload)
    if (!user?._id) {
      router.replace('/auth/login' as any);
      return;
    }
    fetchItems();
  }, [fetchItems, user?._id, authLoading]));

  const handleAdd = async () => {
    if (!user?._id) return;
    setSaving(true);
    try {
      await api.post(`/inventory/${user._id}`, form);
      setShowAdd(false);
      setForm({ ...EMPTY_FORM });
      fetchItems();
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Could not add vehicle. Provide at least year/make/model or a name.');
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = async (item: any) => {
    const newStatus = item.status === 'sold' ? 'available' : 'sold';
    try {
      await api.put(`/inventory/${user?._id}/${item._id}`, { status: newStatus });
      fetchItems();
    } catch {
      showSimpleAlert('Error', 'Could not update status.');
    }
  };

  const handleDelete = (item: any) => {
    showConfirm('Delete Vehicle', `Remove "${item.name}" from inventory?`, async () => {
      try {
        await api.delete(`/inventory/${user?._id}/${item._id}`);
        fetchItems();
      } catch {
        showSimpleAlert('Error', 'Could not delete item.');
      }
    });
  };

  const handleCSVUpload = async () => {
    if (!user?._id) return;
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['text/csv', 'text/comma-separated-values', 'application/csv', '*/*'],
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;
      const file = result.assets[0];
      if (!file.uri) return;
      if (!(file.name || '').toLowerCase().endsWith('.csv')) {
        showSimpleAlert('Unsupported File', 'Please pick a .csv file');
        return;
      }
      setUploading(true);
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const resp = await fetch(file.uri);
        const blob = await resp.blob();
        formData.append('file', blob, file.name || 'inventory.csv');
      } else {
        formData.append('file', { uri: file.uri, name: file.name || 'inventory.csv', type: 'text/csv' } as any);
      }
      const res = await api.post(`/inventory/${user._id}/csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      showSimpleAlert('Import Complete', `${res.data.imported} vehicles imported${res.data.skipped ? `, ${res.data.skipped} rows skipped` : ''}.`);
      fetchItems();
    } catch (e: any) {
      showSimpleAlert('Import Failed', e?.response?.data?.detail || 'Could not import the CSV. Expected columns like: year, make, model, price, color, mileage, stock, vin.');
    } finally {
      setUploading(false);
    }
  };

  const fmtPrice = (p: any) => (p || p === 0) ? `$${Number(p).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '';

  const FILTERS = [
    { key: 'available', label: `Available${counts.available != null ? ` (${counts.available})` : ''}` },
    { key: 'sold', label: `Sold${counts.sold != null ? ` (${counts.sold})` : ''}` },
    { key: 'all', label: 'All' },
  ];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} data-testid="inventory-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, flex: 1 }} numberOfLines={1}>Inventory</Text>
        {['store_manager', 'org_admin', 'super_admin', 'admin'].includes(user?.role || '') && (
          <TouchableOpacity
            style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.card, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12 }}
            onPress={() => router.push('/admin/inventory-feed' as any)}
            data-testid="inventory-feed-btn"
          >
            <Ionicons name="cloud-download-outline" size={16} color={ACCENT} />
            <Text style={{ fontSize: 13, fontWeight: '600', color: ACCENT }}>Feed</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.card, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12 }}
          onPress={handleCSVUpload}
          disabled={uploading}
          data-testid="inventory-csv-btn"
        >
          {uploading ? <ActivityIndicator size="small" color={ACCENT} /> : <Ionicons name="cloud-upload-outline" size={16} color={ACCENT} />}
          <Text style={{ fontSize: 13, fontWeight: '600', color: ACCENT }}>CSV</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: ACCENT, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12 }}
          onPress={() => setShowAdd(true)}
          data-testid="inventory-add-btn"
        >
          <Ionicons name="add" size={16} color="#FFF" />
          <Text style={{ fontSize: 13, fontWeight: '700', color: '#FFF' }}>Add</Text>
        </TouchableOpacity>
      </View>

      {/* Jessi note */}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 10, backgroundColor: `${ACCENT}12`, borderRadius: 10, padding: 10 }}>
        <Ionicons name="sparkles" size={15} color={ACCENT} />
        <Text style={{ fontSize: 13, color: colors.textSecondary, flex: 1 }}>
          Jessi uses this list to answer customer availability & pricing questions live.
        </Text>
      </View>

      {/* Photo reminder banner */}
      {counts.missing_photos > 0 && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 16, marginBottom: 10, backgroundColor: '#FF950014', borderRadius: 10, padding: 10 }} data-testid="inventory-photo-reminder-banner">
          <Ionicons name="camera" size={15} color="#FF9500" />
          <Text style={{ fontSize: 13, color: colors.textSecondary, flex: 1 }}>
            <Text style={{ fontWeight: '700', color: '#FF9500' }}>{counts.missing_photos} in-stock vehicle{counts.missing_photos !== 1 ? 's' : ''} missing photos</Text> - leads get the car&apos;s picture texted automatically once one is added.
          </Text>
        </View>
      )}

      {/* Search */}
      <View style={{ flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 10, paddingHorizontal: 12, height: 40, marginBottom: 10 }}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput
          style={{ flex: 1, fontSize: 15, color: colors.text, marginLeft: 8, height: 40 }}
          placeholder="Search make, model, color, stock #..."
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={fetchItems}
          returnKeyType="search"
          data-testid="inventory-search-input"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => { setSearch(''); setTimeout(fetchItems, 50); }}>
            <Ionicons name="close-circle" size={16} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Status filters */}
      <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginBottom: 10 }}>
        {FILTERS.map(f => {
          const active = statusFilter === f.key;
          return (
            <TouchableOpacity
              key={f.key}
              style={{ paddingHorizontal: 14, height: 32, borderRadius: 16, justifyContent: 'center', backgroundColor: active ? ACCENT : colors.card }}
              onPress={() => setStatusFilter(f.key)}
              data-testid={`inventory-filter-${f.key}`}
            >
              <Text style={{ fontSize: 13, fontWeight: '600', color: active ? '#FFF' : colors.textSecondary }} numberOfLines={1}>{f.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color={ACCENT} />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 10 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchItems(); }} tintColor={colors.textSecondary} />}
        >
          {items.length === 0 ? (
            <View style={{ alignItems: 'center', paddingTop: 50 }}>
              <Ionicons name="car-sport-outline" size={44} color={colors.textSecondary} />
              <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12 }}>No vehicles yet</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 6, paddingHorizontal: 32 }}>
                Add vehicles manually, upload a CSV, or connect a HomeNet/vAuto feed to the inventory webhook.
              </Text>
            </View>
          ) : (
            items.map((item: any) => {
              const a = item.attributes || {};
              const subBits = [a.body_type, a.color, a.mileage ? `${a.mileage} mi` : '', a.stock_number ? `Stock #${a.stock_number}` : ''].filter(Boolean);
              const sold = item.status === 'sold';
              return (
                <View key={item._id} style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14 }} data-testid={`inventory-item-${item._id}`}>
                  <View style={{ flexDirection: 'row', gap: 12 }}>
                    <TouchableOpacity onPress={() => handleAddPhoto(item)} data-testid={`inventory-photo-${item._id}`}>
                      {photoUploadingId === item._id ? (
                        <View style={{ width: 62, height: 62, borderRadius: 10, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }}>
                          <ActivityIndicator size="small" color={ACCENT} />
                        </View>
                      ) : item.photo_url ? (
                        <View>
                          <Image source={{ uri: resolvePhotoUrl(item.photo_url) || '' }} style={{ width: 62, height: 62, borderRadius: 10, backgroundColor: colors.surface }} contentFit="cover" />
                          <View style={{ position: 'absolute', bottom: -4, right: -4, backgroundColor: '#0B0B0D', borderRadius: 9, paddingHorizontal: 5, paddingVertical: 1, flexDirection: 'row', alignItems: 'center', gap: 2, borderWidth: 1, borderColor: colors.border }} data-testid={`inventory-photo-count-${item._id}`}>
                            <Ionicons name="images" size={9} color={colors.textSecondary} />
                            <Text style={{ fontSize: 9, fontWeight: '700', color: colors.textSecondary }}>{(item.photos || []).length || 1}</Text>
                          </View>
                        </View>
                      ) : (
                        <View style={{ width: 62, height: 62, borderRadius: 10, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border, borderStyle: 'dashed' }}>
                          <Ionicons name="camera-outline" size={20} color={colors.textSecondary} />
                          <Text style={{ fontSize: 9, color: colors.textSecondary, marginTop: 2 }}>Photo</Text>
                        </View>
                      )}
                    </TouchableOpacity>
                    <View style={{ flex: 1 }}>
                      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
                        <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, flex: 1 }} numberOfLines={2}>{item.name}</Text>
                        {item.price != null && (
                          <Text style={{ fontSize: 16, fontWeight: '700', color: '#34C759' }}>{fmtPrice(item.price)}</Text>
                        )}
                      </View>
                      {subBits.length > 0 && (
                        <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 3 }} numberOfLines={1}>{subBits.join(' · ')}</Text>
                      )}
                    </View>
                  </View>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 }}>
                    <View style={{ backgroundColor: sold ? '#FF3B3018' : '#34C75918', paddingVertical: 3, paddingHorizontal: 10, borderRadius: 6 }}>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: sold ? '#FF3B30' : '#34C759' }}>{sold ? 'SOLD' : 'AVAILABLE'}</Text>
                    </View>
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity
                      style={{ paddingVertical: 6, paddingHorizontal: 12, borderRadius: 8, backgroundColor: colors.surface }}
                      onPress={() => toggleStatus(item)}
                      data-testid={`inventory-toggle-${item._id}`}
                    >
                      <Text style={{ fontSize: 12, fontWeight: '600', color: colors.text }}>{sold ? 'Mark Available' : 'Mark Sold'}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={{ padding: 6 }}
                      onPress={() => handleDelete(item)}
                      data-testid={`inventory-delete-${item._id}`}
                    >
                      <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })
          )}
        </ScrollView>
      )}

      <PhotoGallerySheet
        visible={!!galleryItem} userId={user?._id || ''} item={galleryItem} colors={colors}
        onClose={() => setGalleryItem(null)} onChanged={applyPhotos}
        onError={(m) => showSimpleAlert('Photos', m)}
      />

      {/* Add Vehicle Modal */}
      <Modal visible={showAdd} animationType="slide" transparent onRequestClose={() => setShowAdd(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '88%' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.surface }}>
              <TouchableOpacity onPress={() => setShowAdd(false)} data-testid="inventory-add-cancel">
                <Text style={{ fontSize: 16, color: colors.textSecondary }}>Cancel</Text>
              </TouchableOpacity>
              <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Add Vehicle</Text>
              <TouchableOpacity onPress={handleAdd} disabled={saving} data-testid="inventory-add-save">
                {saving ? <ActivityIndicator size="small" color={ACCENT} /> : <Text style={{ fontSize: 16, fontWeight: '700', color: ACCENT }}>Save</Text>}
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
              {[
                [{ key: 'year', label: 'Year', kb: 'number-pad' }, { key: 'make', label: 'Make' }],
                [{ key: 'model', label: 'Model' }, { key: 'trim', label: 'Trim' }],
                [{ key: 'color', label: 'Color' }, { key: 'mileage', label: 'Mileage', kb: 'number-pad' }],
                [{ key: 'price', label: 'Price', kb: 'decimal-pad' }, { key: 'stock_number', label: 'Stock #' }],
              ].map((row, ri) => (
                <View key={ri} style={{ flexDirection: 'row', gap: 10, marginBottom: 12 }}>
                  {row.map((f: any) => (
                    <View key={f.key} style={{ flex: 1 }}>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 5 }}>{f.label.toUpperCase()}</Text>
                      <TextInput
                        style={{ backgroundColor: colors.card, borderRadius: 10, padding: 12, fontSize: 15, color: colors.text }}
                        value={(form as any)[f.key]}
                        onChangeText={(v) => setForm(prev => ({ ...prev, [f.key]: v }))}
                        keyboardType={f.kb || 'default'}
                        placeholderTextColor={colors.textSecondary}
                        data-testid={`inventory-form-${f.key}`}
                      />
                    </View>
                  ))}
                </View>
              ))}
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 5 }}>BODY TYPE (OPTIONAL)</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 6 }}>
                {BODY_TYPES.map(bt => {
                  const on = form.body_type === bt;
                  return (
                    <TouchableOpacity
                      key={bt}
                      onPress={() => setForm(prev => ({ ...prev, body_type: on ? '' : bt }))}
                      style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: on ? ACCENT : colors.card, borderWidth: 1, borderColor: on ? ACCENT : colors.border }}
                      testID={`inventory-body-${bt.toLowerCase()}`}
                      {...({ dataSet: { testid: `inventory-body-${bt.toLowerCase()}` } } as any)}
                    >
                      <Text style={{ fontSize: 13, fontWeight: '600', color: on ? '#fff' : colors.text }}>{bt}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 12 }}>
                Jessi uses this when a customer asks for "trucks" or "SUVs". Leave blank and she guesses from the model.
              </Text>
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 5 }}>VIN (OPTIONAL)</Text>
              <TextInput
                style={{ backgroundColor: colors.card, borderRadius: 10, padding: 12, fontSize: 15, color: colors.text, marginBottom: 12 }}
                value={form.vin}
                onChangeText={(v) => setForm(prev => ({ ...prev, vin: v }))}
                autoCapitalize="characters"
                data-testid="inventory-form-vin"
              />
              <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 5 }}>NOTES (OPTIONAL)</Text>
              <TextInput
                style={{ backgroundColor: colors.card, borderRadius: 10, padding: 12, fontSize: 15, color: colors.text, height: 70, textAlignVertical: 'top' }}
                value={form.description}
                onChangeText={(v) => setForm(prev => ({ ...prev, description: v }))}
                multiline
                data-testid="inventory-form-description"
              />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}
