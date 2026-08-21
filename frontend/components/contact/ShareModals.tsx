/**
 * ShareModals — review, template, business card, photo-option, action-sheet
 * and card-template-picker modals for the contact detail screen.
 * Extracted from contact/[id].tsx (render-only; all state lives in the parent).
 */
import React from 'react';
import { View, Text, TouchableOpacity, Modal, ScrollView, FlatList, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

export default function ShareModals(props: any) {
  const {
    s, colors, contact, user, contactId,
    showReviewCardOptions, setShowReviewCardOptions, sendReviewCard, sendingReviewCard,
    showReviewLinks, setShowReviewLinks, storeSlug, reviewLinks, customLinkName, insertReviewLink, setComposerMessage,
    showTemplates, setShowTemplates, templates, selectTemplate,
    showBusinessCard, setShowBusinessCard, sendVCardLink, sendBusinessCardLink,
    sendLandingPageLink, sendShowcaseLink, sendLinkPageLink,
    showLandingPageOptions, setShowLandingPageOptions,
    loadingCampaigns, campaigns, selectedCampaign, setSelectedCampaign,
    showPhotoOptionsModal, setShowPhotoOptionsModal, pickComposerPhoto,
    showCardTemplatePicker, setShowCardTemplatePicker, handleCardTemplateSelect, customCardTypes,
    webActionSheet, setWebActionSheet,
  } = props;
  const router = useRouter();

  return (
    <>
      {/* Review Card Options — choose between branded card or plain link */}
      <Modal visible={showReviewCardOptions} animationType="slide" transparent={true} onRequestClose={() => setShowReviewCardOptions(false)}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowReviewCardOptions(false)}>
          <View style={s.actionSheetContainer}>
            <Text style={[s.actionSheetTitle, { color: colors.text }]}>Request a Review</Text>
            <Text style={[s.actionSheetSubtitle, { color: colors.textSecondary }]}>
              How would you like to send the review request?
            </Text>

            {/* Branded card option */}
            <TouchableOpacity
              style={[s.actionSheetButton, { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 16 }]}
              onPress={sendReviewCard}
              disabled={sendingReviewCard}
              data-testid="send-review-card-btn"
            >
              {sendingReviewCard ? (
                <ActivityIndicator color="#34C759" />
              ) : (
                <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="image" size={20} color="#34C759" />
                </View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={[s.actionSheetButtonText, { color: colors.text }]}>Send Branded Review Card</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
                  MMS with your store logo + "please leave a review"
                </Text>
              </View>
            </TouchableOpacity>

            {/* Plain review link option */}
            <TouchableOpacity
              style={[s.actionSheetButton, { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 16 }]}
              onPress={() => { setShowReviewCardOptions(false); setShowReviewLinks(true); }}
              data-testid="send-review-link-btn"
            >
              <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#007AFF20', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="star" size={20} color="#007AFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[s.actionSheetButtonText, { color: colors.text }]}>Send Review Link</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>Plain text link only</Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowReviewCardOptions(false)}>
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Review Links Action Sheet */}
      <Modal visible={showReviewLinks} animationType="slide" transparent={true}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowReviewLinks(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              {storeSlug && (
                <>
                  <TouchableOpacity
                    style={s.actionSheetButton}
                    data-testid="review-link-imos"
                    onPress={async () => {
                      const firstName = contact.first_name || 'there';
                      const reviewUrl = `https://app.imonsocial.com/review/${storeSlug}?sp=${user?._id}`;
                      setShowReviewLinks(false);
                      try {
                        const shortRes = await api.post('/s/create', {
                          original_url: reviewUrl,
                          link_type: 'review_request',
                          user_id: user?._id,
                          reference_id: contactId,
                          metadata: { contact_id: contactId, platform: 'imos' },
                        });
                        const trackableUrl = shortRes.data?.short_url || reviewUrl;
                        setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${trackableUrl}`);
                      } catch (e) {
                        setComposerMessage(`Hey ${firstName}! We'd love your feedback. Leave us a review here: ${reviewUrl}`);
                      }
                    }}
                  >
                    <Ionicons name="star" size={22} color="#FFD60A" />
                    <Text style={s.actionSheetButtonText}>Send Review Request</Text>
                  </TouchableOpacity>
                  <View style={s.actionSheetDivider} />
                </>
              )}
              {Object.entries(reviewLinks).filter(([_, url]) => url).map(([platformId, url], index, arr) => {
                const platformNames: Record<string, {name: string; icon: string; color: string}> = {
                  google: { name: 'Google Reviews', icon: 'logo-google', color: '#4285F4' },
                  facebook: { name: 'Facebook', icon: 'logo-facebook', color: '#1877F2' },
                  yelp: { name: 'Yelp', icon: 'star', color: '#D32323' },
                  trustpilot: { name: 'Trustpilot', icon: 'shield-checkmark', color: '#00B67A' },
                  dealerrater: { name: 'DealerRater', icon: 'car-sport', color: '#ED8B00' },
                  cars_com: { name: 'Cars.com', icon: 'car', color: '#5C2D91' },
                  custom: { name: customLinkName || 'Custom Link', icon: 'link', color: colors.textSecondary },
                };
                const platform = platformNames[platformId] || platformNames.custom;
                return (
                  <React.Fragment key={platformId}>
                    <TouchableOpacity style={s.actionSheetButton} onPress={() => insertReviewLink(platformId, url as string, platform.name)}>
                      <Ionicons name={platform.icon as any} size={22} color={platform.color} />
                      <Text style={s.actionSheetButtonText}>{platform.name}</Text>
                    </TouchableOpacity>
                    {index < arr.length - 1 && <View style={s.actionSheetDivider} />}
                  </React.Fragment>
                );
              })}
              {!storeSlug && Object.keys(reviewLinks).length === 0 && (
                <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                  <Ionicons name="settings-outline" size={22} color="#007AFF" />
                  <Text style={s.actionSheetButtonText}>Set Up Review Links</Text>
                </TouchableOpacity>
              )}
              {(storeSlug || Object.keys(reviewLinks).length > 0) && (
                <>
                  <View style={s.actionSheetDivider} />
                  <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowReviewLinks(false); router.push('/settings/review-links' as any); }}>
                    <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
                    <Text style={[s.actionSheetButtonText, { color: colors.textSecondary, fontSize: 18 }]}>Manage Review Links</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowReviewLinks(false)}>
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Templates Modal */}
      <Modal visible={showTemplates} animationType="slide" presentationStyle="pageSheet" transparent={true}>
        <TouchableOpacity style={s.toolbarModalOverlay} activeOpacity={1} onPress={() => setShowTemplates(false)}>
          <View style={s.toolbarModal} onStartShouldSetResponder={() => true}>
            <View style={s.toolbarModalHeader}>
              <View style={s.toolbarModalHandle} />
              <Text style={s.toolbarModalTitle}>Message Templates</Text>
            </View>
            <FlatList
              data={templates}
              keyExtractor={(item: any) => item._id}
              style={s.toolbarTemplatesList}
              contentContainerStyle={s.toolbarTemplatesListContent}
              showsVerticalScrollIndicator={true}
              renderItem={({ item: template }: any) => (
                <TouchableOpacity style={s.toolbarTemplateItem} onPress={() => selectTemplate(template)}>
                  <View style={s.toolbarTemplateIcon}>
                    <Ionicons name="document-text" size={20} color="#007AFF" />
                  </View>
                  <View style={s.toolbarTemplateContent}>
                    <Text style={s.toolbarTemplateName}>{template.name}</Text>
                    <Text style={s.toolbarTemplatePreview} numberOfLines={2}>{template.content}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
              ListEmptyComponent={() => (
                <View style={s.toolbarEmptyTemplates}>
                  <Ionicons name="document-text-outline" size={48} color={colors.textSecondary} />
                  <Text style={s.toolbarEmptyTemplatesText}>No templates yet</Text>
                </View>
              )}
            />
            <View style={s.toolbarModalFooter}>
              <TouchableOpacity style={s.toolbarModalCloseBtn} onPress={() => setShowTemplates(false)}>
                <Text style={s.toolbarModalCloseBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Digital Business Card Modal */}
      <Modal visible={showBusinessCard} animationType="slide" presentationStyle="pageSheet" transparent={true}>
        <TouchableOpacity style={s.toolbarModalOverlay} activeOpacity={1} onPress={() => setShowBusinessCard(false)}>
          <View style={[s.toolbarModal, { marginBottom: 40 }]} onStartShouldSetResponder={() => true}>
            <View style={s.toolbarModalHeader}>
              <View style={s.toolbarModalHandle} />
            </View>
            <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 16 }} bounces={false}>
            <View style={s.cardModalContent}>
              <View style={s.cardPreview}>
                <Ionicons name="share-social" size={48} color="#007AFF" />
                <Text style={s.cardPreviewTitle}>Share Your Stuff</Text>
                <Text style={s.cardPreviewDesc}>Choose what you'd like to send to {contact.first_name || 'this contact'}</Text>
              </View>
              <View style={s.shareOptionsContainer}>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendVCardLink} data-testid="share-vcf-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="person-add" size={28} color="#34C759" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Contact (VCF)</Text>
                    <Text style={s.shareOptionDesc}>Send a direct link to save your contact info to their phone</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendBusinessCardLink} data-testid="share-landing-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="card-outline" size={28} color="#007AFF" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Digital Card</Text>
                    <Text style={s.shareOptionDesc}>Send your sleek digital business card</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendLandingPageLink} data-testid="share-landingpage-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="globe-outline" size={28} color="#5856D6" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Landing Page</Text>
                    <Text style={s.shareOptionDesc}>Send your full profile with bio, socials & more</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendShowcaseLink} data-testid="share-showcase-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="images-outline" size={28} color="#FF9500" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Showcase</Text>
                    <Text style={s.shareOptionDesc}>Show off your happy customers & featured work</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity style={s.shareOptionCard} onPress={sendLinkPageLink} data-testid="share-linkpage-btn">
                  <View style={s.shareOptionIcon}>
                    <Ionicons name="link-outline" size={28} color="#AF52DE" />
                  </View>
                  <View style={s.shareOptionContent}>
                    <Text style={s.shareOptionTitle}>Share Link Page</Text>
                    <Text style={s.shareOptionDesc}>Send all your social links in one place</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </TouchableOpacity>

                {/* CRM Timeline Link */}
                <View style={[s.shareOptionCard, { borderTopWidth: 1, borderTopColor: colors.surface, marginTop: 8, paddingTop: 16 }]}>
                  <View style={[s.shareOptionIcon, { backgroundColor: '#C9A96220' }]}>
                    <Ionicons name="open-outline" size={28} color="#C9A962" />
                  </View>
                  <View style={[s.shareOptionContent, { flex: 1 }]}>
                    <Text style={s.shareOptionTitle}>CRM Timeline Link</Text>
                    <Text style={s.shareOptionDesc}>Copy a live activity link for your CRM</Text>
                  </View>
                  <TouchableOpacity
                    style={{ backgroundColor: '#C9A962', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 }}
                    onPress={async () => {
                      try {
                        const res = await api.post(`/crm/timeline-token/${user._id}/${contactId}`);
                        const link = `${api.defaults.baseURL?.replace('/api', '')}/timeline/${res.data.token}`;
                        api.post(`/crm/mark-copied/${user._id}/${contactId}`).catch(() => {});

                        // Use native Share Sheet on mobile (most reliable on iOS)
                        if (typeof navigator !== 'undefined' && navigator.share) {
                          try {
                            await navigator.share({
                              title: `${contact.first_name || ''} ${contact.last_name || ''} — Activity Timeline`.trim(),
                              url: link,
                            });
                            return;
                          } catch (shareErr: any) {
                            // User cancelled share — still show the link
                            if (shareErr?.name === 'AbortError') return;
                          }
                        }

                        // Desktop fallback: clipboard
                        try {
                          await Clipboard.setStringAsync(link);
                          showSimpleAlert('CRM Link Copied!', 'Paste this into your CRM. It stays up-to-date automatically.');
                        } catch {
                          // Last resort: show the link so user can manually copy
                          showSimpleAlert('CRM Timeline Link', link);
                        }
                      } catch (e: any) {
                        console.error('CRM link error:', e?.response?.data || e?.message || e);
                        showSimpleAlert('Error', e?.response?.data?.detail || 'Could not generate CRM link');
                      }
                    }}
                    data-testid="copy-crm-link-btn"
                  >
                    <Text style={{ color: '#000', fontWeight: '700', fontSize: 15 }}>Copy</Text>
                  </TouchableOpacity>
                </View>
              </View>
              {showLandingPageOptions && (
                <View style={s.landingPageOptions}>
                  <View style={s.landingPageOptionsHeader}>
                    <TouchableOpacity onPress={() => setShowLandingPageOptions(false)}>
                      <Ionicons name="arrow-back" size={24} color="#007AFF" />
                    </TouchableOpacity>
                    <Text style={s.landingPageOptionsTitle}>Landing Page Options</Text>
                  </View>
                  <Text style={s.campaignPickerLabel}>Start them on a campaign (optional):</Text>
                  {loadingCampaigns ? (
                    <ActivityIndicator size="small" color="#007AFF" style={{ marginVertical: 20 }} />
                  ) : campaigns.length === 0 ? (
                    <View style={s.noCampaigns}>
                      <Text style={s.noCampaignsText}>No active campaigns</Text>
                      <Text style={s.noCampaignsSubtext}>Create campaigns in the Campaigns tab</Text>
                    </View>
                  ) : (
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.campaignScroller} contentContainerStyle={s.campaignScrollerContent}>
                      <TouchableOpacity style={[s.campaignChip, !selectedCampaign && s.campaignChipSelected]} onPress={() => setSelectedCampaign(null)}>
                        <Text style={[s.campaignChipText, !selectedCampaign && s.campaignChipTextSelected]}>None</Text>
                      </TouchableOpacity>
                      {campaigns.map((campaign: any) => (
                        <TouchableOpacity key={campaign.id || campaign._id} style={[s.campaignChip, selectedCampaign === (campaign.id || campaign._id) && s.campaignChipSelected]} onPress={() => setSelectedCampaign(campaign.id || campaign._id)}>
                          <Text style={[s.campaignChipText, selectedCampaign === (campaign.id || campaign._id) && s.campaignChipTextSelected]}>{campaign.name}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  )}
                  <TouchableOpacity style={s.sendCardButton} onPress={sendBusinessCardLink} data-testid="send-card-btn">
                    <Ionicons name="paper-plane" size={20} color="#FFF" />
                    <Text style={s.sendCardButtonText}>{selectedCampaign ? 'Send Card + Start Campaign' : 'Send Landing Page'}</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
            </ScrollView>
            <View style={s.toolbarModalFooter}>
              <TouchableOpacity style={s.toolbarModalCloseBtn} onPress={() => { setShowBusinessCard(false); setShowLandingPageOptions(false); }}>
                <Text style={s.toolbarModalCloseBtnText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Photo & Card Action Sheet (Web/PWA) */}
      <Modal visible={showPhotoOptionsModal} animationType="slide" transparent={true} onRequestClose={() => setShowPhotoOptionsModal(false)}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setShowPhotoOptionsModal(false)}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              <TouchableOpacity style={s.actionSheetButton} onPress={() => { setShowPhotoOptionsModal(false); pickComposerPhoto(); }} data-testid="photo-option-add">
                <Ionicons name="image-outline" size={22} color="#007AFF" />
                <Text style={s.actionSheetButtonText}>Add a Photo</Text>
              </TouchableOpacity>
              <View style={s.actionSheetDivider} />
              <View style={{ paddingVertical: 12, paddingHorizontal: 16 }}>
                <Text style={{ fontSize: 15, color: colors.textSecondary, fontWeight: '600', marginBottom: 10, textAlign: 'center' }}>CREATE A CARD</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingHorizontal: 4 }}>
                  {[
                    { type: 'congrats', label: 'Congrats', color: '#C9A962', icon: 'trophy' },
                    { type: 'birthday', label: 'Birthday', color: '#FF2D55', icon: 'gift' },
                    { type: 'holiday', label: 'Holiday', color: '#5AC8FA', icon: 'snow' },
                    { type: 'thankyou', label: 'Thank You', color: '#34C759', icon: 'thumbs-up' },
                    { type: 'anniversary', label: 'Anniversary', color: '#FF6B6B', icon: 'heart' },
                    { type: 'welcome', label: 'Welcome', color: '#007AFF', icon: 'hand-left' },
                    ...customCardTypes,
                  ].map((item: any) => (
                    <TouchableOpacity
                      key={item.type}
                      style={{ alignItems: 'center', backgroundColor: `${item.color}15`, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14, minWidth: 80 }}
                      onPress={() => { setShowPhotoOptionsModal(false); handleCardTemplateSelect(item.type); }}
                      data-testid={`card-template-${item.type}`}
                    >
                      <Ionicons name={item.icon as any} size={24} color={item.color} />
                      <Text style={{ fontSize: 14, fontWeight: '600', color: item.color, marginTop: 6 }}>{item.label}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setShowPhotoOptionsModal(false)} data-testid="photo-option-cancel">
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Web Action Sheet for Automation Chips */}
      <Modal visible={webActionSheet.visible} animationType="slide" transparent={true} onRequestClose={() => setWebActionSheet((prev: any) => ({ ...prev, visible: false }))}>
        <TouchableOpacity style={s.actionSheetOverlay} activeOpacity={1} onPress={() => setWebActionSheet((prev: any) => ({ ...prev, visible: false }))}>
          <View style={s.actionSheetContainer} onStartShouldSetResponder={() => true}>
            <View style={s.actionSheetGroup}>
              <View style={{ paddingVertical: 14, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: colors.border }}>
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>{webActionSheet.title}</Text>
              </View>
              {webActionSheet.options.map((option: any, idx: number) => (
                <React.Fragment key={idx}>
                  <TouchableOpacity 
                    style={s.actionSheetButton} 
                    onPress={() => { setWebActionSheet((prev: any) => ({ ...prev, visible: false })); option.onPress(); }}
                    data-testid={`action-sheet-${option.label.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <Ionicons name={option.icon as any} size={22} color={option.color} />
                    <Text style={[s.actionSheetButtonText, { color: option.color }]}>{option.label}</Text>
                  </TouchableOpacity>
                  {idx < webActionSheet.options.length - 1 && <View style={s.actionSheetDivider} />}
                </React.Fragment>
              ))}
            </View>
            <TouchableOpacity style={s.actionSheetCancel} onPress={() => setWebActionSheet((prev: any) => ({ ...prev, visible: false }))} data-testid="action-sheet-cancel">
              <Text style={s.actionSheetCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Card Template Picker */}
      <Modal visible={showCardTemplatePicker} animationType="slide" transparent onRequestClose={() => setShowCardTemplatePicker(false)}>
        <TouchableOpacity style={s.sendPickerOverlay} activeOpacity={1} onPress={() => setShowCardTemplatePicker(false)}>
          <TouchableOpacity activeOpacity={1} onPress={() => {}}>
            <View style={[s.sendPickerSheet, { maxHeight: '85%' }]}>
              <View style={s.sendPickerHandle} />
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingBottom: 10 }}>
                <Text style={s.sendPickerTitle}>Choose a Card Template</Text>
                <TouchableOpacity onPress={() => setShowCardTemplatePicker(false)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                  <Ionicons name="close-circle" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
              <ScrollView
                bounces={true}
                showsVerticalScrollIndicator={true}
                keyboardShouldPersistTaps="handled"
                nestedScrollEnabled={true}
                contentContainerStyle={{ paddingBottom: 30 }}
              >
              {[
                { type: 'congrats', label: 'Congratulations', sub: 'Celebrate a purchase or milestone', color: '#C9A962', icon: 'trophy' },
                { type: 'birthday', label: 'Happy Birthday', sub: 'Send birthday wishes', color: '#FF2D55', icon: 'gift' },
                { type: 'anniversary', label: 'Anniversary', sub: 'Celebrate their anniversary', color: '#FF6B6B', icon: 'heart' },
                { type: 'thankyou', label: 'Thank You', sub: 'Show your appreciation', color: '#34C759', icon: 'thumbs-up' },
                { type: 'welcome', label: 'Welcome', sub: 'Welcome a new customer', color: '#007AFF', icon: 'hand-left' },
                { type: 'holiday', label: 'Holiday', sub: 'Seasonal greetings', color: '#5AC8FA', icon: 'snow' },
                ...customCardTypes,
              ].map((item: any) => (
                <TouchableOpacity
                  key={item.type}
                  style={s.sendPickerItem}
                  onPress={() => handleCardTemplateSelect(item.type)}
                  activeOpacity={0.7}
                  data-testid={`card-template-${item.type}`}
                >
                  <View style={[s.sendPickerIcon, { backgroundColor: `${item.color}20` }]}>
                    <Ionicons name={item.icon as any} size={20} color={item.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.sendPickerLabel}>{item.label}</Text>
                    <Text style={s.sendPickerSub}>{item.sub}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
                </TouchableOpacity>
              ))}
              </ScrollView>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>
    </>
  );
}
