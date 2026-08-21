/**
 * GalleryModal — full-screen photo gallery (grid, reel viewer, upload & manage).
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import api from '../../services/api';
import { showConfirm, showSimpleAlert } from '../../services/alert';
import { resolvePhotoUrl } from '../../utils/photoUrl';

export default function GalleryModal(props: any) {
  const {
    s, insets, screenWidth, user, contactId, setContact,
    showPhotoViewer, setShowPhotoViewer, fullPhotoLoading,
    allPhotos, setAllPhotos, selectedPhotoIndex, setSelectedPhotoIndex, setFullPhoto,
    galleryWidth, setGalleryWidth, photoReelRef,
    runPendingPick, requestAddPhotoFromGallery, preloadGalleryPhotos, usePhotoForCard,
    showToast,
  } = props;

  return (
    <Modal visible={showPhotoViewer} animationType="slide" transparent={false} onDismiss={runPendingPick} onRequestClose={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}>
      {/* NOTE: react-native-safe-area-context returns 0 insets inside a RN Modal
          (it renders outside the SafeAreaProvider tree), so we apply the insets
          captured at the screen level explicitly instead of using SafeAreaView here. */}
      <View style={{ flex: 1, backgroundColor: '#000' }}>
      <View style={s.galleryRoot}>
        {/* Header */}
        <View style={[s.galleryTopBar, { paddingTop: insets.top + 12 }]}>
          <TouchableOpacity
            style={s.galleryCloseBtn}
            onPress={() => { setShowPhotoViewer(false); setFullPhoto(null); setAllPhotos([]); setSelectedPhotoIndex(-1); }}
            data-testid="close-photo-viewer"
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Ionicons name="close" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.galleryTopTitle}>
            {selectedPhotoIndex >= 0 ? `${selectedPhotoIndex + 1} of ${allPhotos.length}` : 'Photos'}
          </Text>
          <TouchableOpacity
            style={s.galleryUploadBtn}
            onPress={requestAddPhotoFromGallery}
            data-testid="gallery-upload-btn"
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Ionicons name="camera" size={22} color="#C9A962" />
          </TouchableOpacity>
        </View>

        {fullPhotoLoading ? (
          /* === SHIMMER SKELETON GRID === */
          <View style={{ flex: 1, padding: 0 }}>
            <View
              style={s.galleryGrid}
              onLayout={(e: any) => setGalleryWidth(e.nativeEvent.layout.width)}
            >
              {[0,1,2,3,4,5].map(i => {
                const sz = galleryWidth > 0 ? Math.floor((galleryWidth - 2) / 3) : 120;
                return (
                  <View key={i} style={{ width: sz, height: sz, backgroundColor: '#1a1a1a' }} data-testid={`shimmer-${i}`} />
                );
              })}
            </View>
          </View>
        ) : selectedPhotoIndex >= 0 && allPhotos.length > 0 ? (
          /* === FULL-SCREEN VIEWER === */
          <View style={{ flex: 1 }}>
            <ScrollView
              ref={photoReelRef}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              scrollEventThrottle={16}
              onLayout={() => {
                // Scroll to the tapped photo after layout — more reliable than FlatList initialScrollIndex on web
                if (selectedPhotoIndex > 0 && photoReelRef.current) {
                  setTimeout(() => {
                    photoReelRef.current?.scrollTo({ x: selectedPhotoIndex * screenWidth, animated: false });
                  }, 50);
                }
              }}
              onScroll={(e: any) => {
                const idx = Math.round(e.nativeEvent.contentOffset.x / screenWidth);
                if (idx >= 0 && idx < allPhotos.length && idx !== selectedPhotoIndex) {
                  setSelectedPhotoIndex(idx);
                  setFullPhoto(allPhotos[idx]?.url || null);
                }
              }}
              style={{ flex: 1 }}
              data-testid="photo-reel"
            >
              {allPhotos.map((item: any, i: number) => {
                const screenH = Dimensions.get('window').height;
                const imgH = screenH - 200;
                return (
                  <View key={`reel-${i}`} style={{ width: screenWidth, height: imgH, justifyContent: 'center', alignItems: 'center' }}>
                    <Image
                      source={{ uri: item.url }}
                      style={{ width: screenWidth, height: imgH }}
                      contentFit="contain"
                      transition={200}
                      cachePolicy="memory-disk"
                    />
                  </View>
                );
              })}
            </ScrollView>
            {/* Bottom action bar */}
            <View style={[s.viewerBottomBar, { paddingBottom: insets.bottom + 12 }]}>
              <View style={{ flex: 1 }}>
                <Text style={s.viewerLabel} numberOfLines={1}>
                  {allPhotos[selectedPhotoIndex]?.type === 'profile' ? 'Profile Photo' : (allPhotos[selectedPhotoIndex]?.label || 'Photo')}
                </Text>
                {allPhotos[selectedPhotoIndex]?.date && (
                  <Text style={s.viewerDate}>{new Date(allPhotos[selectedPhotoIndex].date).toLocaleDateString()}</Text>
                )}
              </View>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TouchableOpacity
                  style={s.viewerActionBtn}
                  onPress={() => { setSelectedPhotoIndex(-1); setFullPhoto(null); }}
                  data-testid="back-to-gallery-grid"
                >
                  <Ionicons name="grid-outline" size={18} color="#FFF" />
                </TouchableOpacity>
                {/* Delete photo button */}
                <TouchableOpacity
                  style={[s.viewerActionBtn, { backgroundColor: '#FF3B30' }]}
                  onPress={() => {
                    const photo = allPhotos[selectedPhotoIndex];
                    if (!photo) return;
                    const isProfile = photo.type === 'profile';
                    showConfirm(
                      isProfile ? 'Remove Profile Photo' : 'Delete Photo',
                      isProfile
                        ? 'This will remove the profile photo. The next photo in history will become the new profile photo.'
                        : 'Are you sure you want to delete this photo? This cannot be undone.',
                      async () => {
                        try {
                          await api.delete(`/contacts/${user?._id}/${contactId}/photos`, { data: { photo_url: photo.url, photo_type: photo.type } });
                          if (isProfile) {
                            setContact((prev: any) => ({ ...prev, photo: null, photo_url: null, photo_thumbnail: null, photo_path: null }));
                          }
                          showToast('Photo deleted', 'success');
                          setSelectedPhotoIndex(-1); setFullPhoto(null);
                          preloadGalleryPhotos();
                        } catch { showSimpleAlert('Error', 'Failed to delete photo'); }
                      }
                    );
                  }}
                  data-testid="delete-photo-btn"
                >
                  <Ionicons name="trash" size={18} color="#FFF" />
                </TouchableOpacity>
                {allPhotos[selectedPhotoIndex]?.type !== 'profile' && (
                  <TouchableOpacity
                    style={[s.viewerActionBtn, { backgroundColor: '#C9A962' }]}
                    onPress={async () => {
                      const photoUrl = allPhotos[selectedPhotoIndex]?.url;
                      if (!photoUrl) return;
                      try {
                        const r = await api.patch(`/contacts/${user._id}/${contactId}/profile-photo`, { photo_url: photoUrl });
                        const durable = r.data?.photo_url ? resolvePhotoUrl(r.data.photo_url) : photoUrl;
                        setContact((prev: any) => ({ ...prev, photo: durable, photo_url: durable, photo_thumbnail: durable }));
                        showToast('Profile photo updated!', 'success');
                        // Refresh gallery and go back to grid
                        setSelectedPhotoIndex(-1); setFullPhoto(null);
                        preloadGalleryPhotos();
                      } catch { showSimpleAlert('Error', 'Failed to update profile photo'); }
                    }}
                    data-testid="set-as-profile-btn"
                  >
                    <Ionicons name="person-circle" size={18} color="#000" />
                  </TouchableOpacity>
                )}
                <TouchableOpacity
                  style={[s.viewerActionBtn, { backgroundColor: '#5856D6' }]}
                  onPress={() => usePhotoForCard(allPhotos[selectedPhotoIndex]?.url)}
                  data-testid="use-for-card-btn"
                >
                  <Ionicons name="gift" size={18} color="#FFF" />
                </TouchableOpacity>
              </View>
            </View>
          </View>
        ) : allPhotos.length > 0 ? (
          /* === SECTIONED 3-COLUMN GRID (Texted In · Sent · Cards · Profile) === */
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }}>
            <View onLayout={(e: any) => setGalleryWidth(e.nativeEvent.layout.width)}>
              {galleryWidth > 0 && (() => {
                const tileSize = Math.floor((galleryWidth - 2) / 3);
                const indexed = allPhotos.map((p: any, i: number) => ({ ...p, _gi: i }));
                const SECTIONS: { title: string; types: string[] }[] = [
                  { title: 'Texted In', types: ['message_in'] },
                  { title: 'You Sent', types: ['message_out'] },
                  { title: 'Cards', types: ['congrats', 'birthday'] },
                  { title: 'Profile', types: ['profile', 'history'] },
                ];
                const renderTile = (photo: any) => {
                  const isProfile = photo.type === 'profile';
                  return (
                    <TouchableOpacity
                      key={`${photo.type}-${photo._gi}`}
                      activeOpacity={0.85}
                      onPress={() => { setSelectedPhotoIndex(photo._gi); setFullPhoto(photo.url); }}
                      data-testid={`gallery-tile-${photo._gi}`}
                      style={{ width: tileSize, height: tileSize, overflow: 'hidden', position: 'relative', backgroundColor: '#111' }}
                    >
                      <Image
                        source={{ uri: photo.thumbnail_url || photo.url }}
                        style={{ width: tileSize, height: tileSize }}
                        contentFit="cover"
                        transition={250}
                        cachePolicy="memory-disk"
                      />
                      {isProfile && (
                        <View style={s.profileBadge} data-testid="profile-badge">
                          <Ionicons name="person-circle" size={14} color="#C9A962" />
                        </View>
                      )}
                      {!isProfile && (
                        <TouchableOpacity
                          style={s.setProfileOverlay}
                          onPress={async (e: any) => {
                            e.stopPropagation?.();
                            try {
                              const r = await api.patch(`/contacts/${user._id}/${contactId}/profile-photo`, { photo_url: photo.url });
                              const durable = r.data?.photo_url ? resolvePhotoUrl(r.data.photo_url) : photo.url;
                              setContact((prev: any) => ({ ...prev, photo: durable, photo_url: durable, photo_thumbnail: durable }));
                              showToast('Profile photo updated!', 'success');
                              preloadGalleryPhotos();
                            } catch { showSimpleAlert('Error', 'Failed to update'); }
                          }}
                          data-testid={`set-profile-${photo._gi}`}
                          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                        >
                          <Ionicons name="person-circle-outline" size={16} color="#FFF" />
                        </TouchableOpacity>
                      )}
                    </TouchableOpacity>
                  );
                };
                return SECTIONS.map((sec) => {
                  const items = indexed.filter((p: any) => sec.types.includes(p.type));
                  if (items.length === 0) return null;
                  return (
                    <View key={sec.title} data-testid={`gallery-section-${sec.title.toLowerCase().replace(/\s+/g, '-')}`}>
                      <Text style={s.gallerySectionHeader}>{sec.title} · {items.length}</Text>
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 1 }}>
                        {items.map(renderTile)}
                      </View>
                    </View>
                  );
                });
              })()}
            </View>
          </ScrollView>
        ) : (
          /* === EMPTY STATE === */
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 40 }}>
            <Ionicons name="images-outline" size={48} color="rgba(255,255,255,0.15)" />
            <Text style={{ color: 'rgba(255,255,255,0.4)', fontSize: 18, marginTop: 12, textAlign: 'center' }}>No photos yet</Text>
            <TouchableOpacity
              style={{ marginTop: 20, backgroundColor: '#C9A962', borderRadius: 20, paddingHorizontal: 24, paddingVertical: 10 }}
              onPress={requestAddPhotoFromGallery}
              data-testid="gallery-empty-upload"
            >
              <Text style={{ color: '#000', fontWeight: '700', fontSize: 16 }}>Add Photo</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
      </View>
    </Modal>
  );
}
