import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  Platform,
  Linking,
  Image,
  Modal,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

const { width } = Dimensions.get('window');
const isWeb = Platform.OS === 'web';

const HANDSHAKE_IMAGE = 'https://static.prod-images.emergentagent.com/jobs/aca65436-af09-4c87-a476-6757d45879e3/images/8f2bbe5337ce1d58d812afb189af3569f807308ff8c36bf5d0c051e6562b1a0c.png';
const IMOS_LOGO = 'https://customer-assets.emergentagent.com/job_35683d39-9c8e-4a2d-a3f7-89b34db8b170/artifacts/g39ale0a_ChatGPT%20Image%20Feb%2023%2C%202026%2C%2004_06_33%20PM.png';

// App-consistent Design Colors
const COLORS = {
  background: '#000000',
  surface: '#0A0A0A',
  elevated: '#1C1C1E',
  card: '#141416',
  accent: '#007AFF', // Blue accent - matches app
  accentLight: '#5AC8FA',
  blue: '#007AFF',
  green: '#34C759',
  purple: '#AF52DE',
  orange: '#FF9500',
  yellow: '#FFD60A',
  pink: '#FF375F',
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A0A5',
  textTertiary: '#6E6E73',
  border: 'rgba(255, 255, 255, 0.08)',
  gradientStart: '#1a1a2e',
  gradientEnd: '#000000',
};

const features = [
  {
    icon: 'chatbubbles',
    title: 'Smart Messaging',
    description: 'AI-powered conversations that help you close more deals with personalized follow-ups.',
    color: '#007AFF',
  },
  {
    icon: 'card',
    title: 'Digital Business Cards',
    description: 'Share your contact info instantly. One tap saves you directly to their phone.',
    color: '#34C759',
  },
  {
    icon: 'trophy',
    title: 'Leaderboards & Gamification',
    description: 'Motivate your team with real-time rankings and performance tracking.',
    color: '#FFD60A',
  },
  {
    icon: 'megaphone',
    title: 'Automated Campaigns',
    description: 'Set it and forget it. Nurture leads with intelligent drip campaigns.',
    color: '#FF9500',
  },
  {
    icon: 'mic',
    title: 'Voice AI Assistant',
    description: 'Meet Jessi - your AI assistant that answers questions and helps your team 24/7.',
    color: '#AF52DE',
  },
  {
    icon: 'analytics',
    title: 'Real-Time Analytics',
    description: 'Track performance, measure ROI, and make data-driven decisions.',
    color: '#FF375F',
  },
];

const testimonials = [
  {
    name: 'Marcus Johnson',
    role: 'Sales Director',
    company: 'Premier Auto Group',
    quote: "iMOS transformed how our team communicates with customers. We've seen a 40% increase in follow-up response rates.",
    avatar: 'MJ',
  },
  {
    name: 'Sarah Chen',
    role: 'General Manager',
    company: 'Luxury Motors',
    quote: "The digital business cards alone have paid for themselves. Customers love the professional touch.",
    avatar: 'SC',
  },
  {
    name: 'David Rodriguez',
    role: 'BDC Manager',
    company: 'Coastal Automotive',
    quote: "Jessi AI has become an essential part of our training. New hires get up to speed faster than ever.",
    avatar: 'DR',
  },
];

export default function IMOSLandingPage() {
  const [scrollY, setScrollY] = useState(0);
  const scrollViewRef = React.useRef<ScrollView>(null);
  const router = useRouter();
  
  // Demo modal state
  const [showDemoModal, setShowDemoModal] = useState(false);
  const [demoForm, setDemoForm] = useState({
    name: '',
    email: '',
    phone: '',
    company: '',
    message: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  
  // Section positions for scrolling
  const sectionRefs = {
    features: React.useRef<View>(null),
    howItWorks: React.useRef<View>(null),
    pricing: React.useRef<View>(null),
    testimonials: React.useRef<View>(null),
    faq: React.useRef<View>(null),
  };
  
  const [sectionPositions, setSectionPositions] = useState<{[key: string]: number}>({});

  const handleGetStarted = () => {
    router.push('/auth/signup');
  };

  const handleSignIn = () => {
    router.push('/auth/login');
  };

  const handleScheduleDemo = () => {
    setShowDemoModal(true);
    setSubmitSuccess(false);
  };
  
  const handleDemoSubmit = async () => {
    if (!demoForm.name || !demoForm.email || !demoForm.phone) {
      alert('Please fill in all required fields');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const API_URL = process.env.EXPO_PUBLIC_API_URL || process.env.REACT_APP_BACKEND_URL || '';
      const response = await fetch(`${API_URL}/api/demo-requests`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: demoForm.name,
          email: demoForm.email,
          phone: demoForm.phone,
          company: demoForm.company,
          message: demoForm.message,
          source: 'website_demo_request',
        }),
      });
      
      if (response.ok) {
        setSubmitSuccess(true);
        setDemoForm({ name: '', email: '', phone: '', company: '', message: '' });
      } else {
        alert('Something went wrong. Please try again.');
      }
    } catch (error) {
      console.error('Demo request error:', error);
      alert('Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const scrollToSection = (sectionKey: string) => {
    const position = sectionPositions[sectionKey];
    if (position !== undefined && scrollViewRef.current) {
      scrollViewRef.current.scrollTo({ y: position - 80, animated: true });
    }
  };
  
  const handleSectionLayout = (sectionKey: string, y: number) => {
    setSectionPositions(prev => ({ ...prev, [sectionKey]: y }));
  };

  return (
    <>
    <ScrollView
      ref={scrollViewRef}
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      onScroll={(e) => setScrollY(e.nativeEvent.contentOffset.y)}
      scrollEventThrottle={16}
    >
      {/* Navigation */}
      <View style={styles.nav}>
        <View style={styles.navContent}>
          <View style={styles.logoContainer}>
            <Image 
              source={{ uri: IMOS_LOGO }} 
              style={styles.navLogo}
              resizeMode="contain"
            />
          </View>
          <View style={styles.navLinks}>
            <TouchableOpacity style={styles.navLink} onPress={() => scrollToSection('features')}>
              <Text style={styles.navLinkText}>Features</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.navLink} onPress={() => scrollToSection('howItWorks')}>
              <Text style={styles.navLinkText}>How It Works</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.navLink} onPress={() => scrollToSection('pricing')}>
              <Text style={styles.navLinkText}>Pricing</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.navLink} onPress={() => scrollToSection('testimonials')}>
              <Text style={styles.navLinkText}>Testimonials</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.navLink} onPress={() => scrollToSection('faq')}>
              <Text style={styles.navLinkText}>FAQ</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.navLink} onPress={handleSignIn}>
              <Text style={styles.navLinkText}>Sign In</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.ctaButtonSmall} onPress={handleGetStarted}>
              <Text style={styles.ctaButtonSmallText}>Get Started</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* Hero Section */}
      <View style={styles.hero}>
        <View style={styles.heroRow}>
          {/* Left side - Text content */}
          <View style={styles.heroTextContent}>
            {/* Category Badge */}
            <View style={styles.categoryBadge}>
              <Text style={styles.categoryText}>RELATIONSHIP MANAGEMENT SYSTEM</Text>
            </View>
            
            {/* Colorful Tagline */}
            <View style={styles.taglineContainer}>
              <Text style={styles.taglineText}>
                <Text style={styles.taglineI}>i</Text>
                <Text style={styles.taglineApostrophe}>'</Text>
                <Text style={styles.taglineM}>M</Text>
                <Text style={styles.taglineSpace}> </Text>
                <Text style={styles.taglineOld}>Old</Text>
                <Text style={styles.taglineSpace}> </Text>
                <Text style={styles.taglineSchool}>School</Text>
              </Text>
              <Text style={styles.taglineSubtext}>with modern tools</Text>
            </View>
            
            <Text style={styles.heroSubtitle}>
              Built on timeless relationship principles and powered by modern automation, 
              this platform ensures every customer feels remembered. The system handles the 
              consistency... so you can focus on authentic human connection without anyone 
              falling through the cracks.
            </Text>
            
            <View style={styles.heroButtons}>
              <TouchableOpacity style={styles.ctaButton} onPress={handleGetStarted}>
                <Text style={styles.ctaButtonText}>Start Free Trial</Text>
                <Ionicons name="arrow-forward" size={20} color="#000" />
              </TouchableOpacity>
              <TouchableOpacity style={styles.secondaryButton} onPress={handleScheduleDemo}>
                <Text style={styles.secondaryButtonText}>Schedule a Demo</Text>
              </TouchableOpacity>
            </View>
            
            <View style={styles.heroStats}>
              <View style={styles.heroStat}>
                <Text style={styles.heroStatNumber}>500+</Text>
                <Text style={styles.heroStatLabel}>Active Teams</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStat}>
                <Text style={styles.heroStatNumber}>2M+</Text>
                <Text style={styles.heroStatLabel}>Messages Sent</Text>
              </View>
              <View style={styles.heroStatDivider} />
              <View style={styles.heroStat}>
                <Text style={styles.heroStatNumber}>98%</Text>
                <Text style={styles.heroStatLabel}>Satisfaction</Text>
              </View>
            </View>
          </View>
          
          {/* Right side - Phone mockup */}
          <View style={styles.phoneContainer}>
            <View style={styles.phoneMockup}>
              <View style={styles.phoneNotch} />
              <View style={styles.phoneScreen}>
                <View style={styles.messagesContainer}>
                  {/* Outgoing message */}
                  <View style={styles.messageOutgoing}>
                    <Text style={styles.messageOutgoingText}>
                      Hey Sarah! Can you believe it's been a year since you got your Civic? Time flies! How's it treating you?
                    </Text>
                    <Text style={styles.messageTime}>10:32 AM</Text>
                  </View>
                  
                  {/* Incoming message */}
                  <View style={styles.messageIncoming}>
                    <Text style={styles.messageIncomingText}>
                      Oh wow, already a year?! It's been amazing honestly. Best decision I made!
                    </Text>
                    <Text style={styles.messageTimeIncoming}>10:34 AM</Text>
                  </View>
                  
                  {/* Outgoing message */}
                  <View style={styles.messageOutgoing}>
                    <Text style={styles.messageOutgoingText}>
                      So glad to hear that! Let me know if you ever need anything. We're running a service special this month too 🔧
                    </Text>
                    <Text style={styles.messageTime}>10:35 AM</Text>
                  </View>
                  
                  {/* Incoming message */}
                  <View style={styles.messageIncoming}>
                    <Text style={styles.messageIncomingText}>
                      Actually perfect timing - I was just thinking about an oil change. I'll stop by Saturday!
                    </Text>
                    <Text style={styles.messageTimeIncoming}>10:37 AM</Text>
                  </View>
                </View>
              </View>
              <View style={styles.phoneHomeBar} />
            </View>
          </View>
        </View>
      </View>

      {/* Features Section */}
      <View 
        style={styles.section}
        onLayout={(e) => handleSectionLayout('features', e.nativeEvent.layout.y)}
      >
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>FEATURES</Text>
          <Text style={styles.sectionTitle}>Everything You Need to Win</Text>
          <Text style={styles.sectionSubtitle}>
            Powerful tools designed for modern sales teams who value authentic connections.
          </Text>
        </View>
        
        <View style={styles.featuresGrid}>
          {features.map((feature, index) => (
            <View key={index} style={styles.featureCard}>
              <View style={[styles.featureIcon, { backgroundColor: `${feature.color}20` }]}>
                <Ionicons name={feature.icon as any} size={28} color={feature.color} />
              </View>
              <Text style={styles.featureTitle}>{feature.title}</Text>
              <Text style={styles.featureDescription}>{feature.description}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* How It Works */}
      <View 
        style={[styles.section, styles.sectionDark]}
        onLayout={(e) => handleSectionLayout('howItWorks', e.nativeEvent.layout.y)}
      >
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>HOW IT WORKS</Text>
          <Text style={styles.sectionTitle}>Get Started in Minutes</Text>
        </View>
        
        <View style={styles.stepsContainer}>
          <View style={styles.step}>
            <View style={[styles.stepNumber, { backgroundColor: COLORS.blue }]}>
              <Text style={styles.stepNumberText}>1</Text>
            </View>
            <Text style={styles.stepTitle}>Connect Your Team</Text>
            <Text style={styles.stepDescription}>
              Invite your team members and set up your organization in just a few clicks.
            </Text>
          </View>
          
          <View style={styles.stepConnector} />
          
          <View style={styles.step}>
            <View style={[styles.stepNumber, { backgroundColor: COLORS.green }]}>
              <Text style={styles.stepNumberText}>2</Text>
            </View>
            <Text style={styles.stepTitle}>Import Your Contacts</Text>
            <Text style={styles.stepDescription}>
              Sync your existing customer database or start fresh with our easy import tools.
            </Text>
          </View>
          
          <View style={styles.stepConnector} />
          
          <View style={styles.step}>
            <View style={[styles.stepNumber, { backgroundColor: COLORS.purple }]}>
              <Text style={styles.stepNumberText}>3</Text>
            </View>
            <Text style={styles.stepTitle}>Start Engaging</Text>
            <Text style={styles.stepDescription}>
              Send personalized messages, share your digital card, and watch your relationships grow.
            </Text>
          </View>
        </View>
      </View>

      {/* Testimonials */}
      <View 
        style={styles.section}
        onLayout={(e) => handleSectionLayout('testimonials', e.nativeEvent.layout.y)}
      >
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>TESTIMONIALS</Text>
          <Text style={styles.sectionTitle}>Loved by Sales Teams</Text>
        </View>
        
        <View style={styles.testimonialsGrid}>
          {testimonials.map((testimonial, index) => (
            <View key={index} style={styles.testimonialCard}>
              <View style={styles.testimonialStars}>
                {[...Array(5)].map((_, i) => (
                  <Ionicons key={i} name="star" size={16} color={COLORS.yellow} />
                ))}
              </View>
              <Text style={styles.testimonialQuote}>"{testimonial.quote}"</Text>
              <View style={styles.testimonialAuthor}>
                <View style={[styles.testimonialAvatar, { backgroundColor: [COLORS.blue, COLORS.green, COLORS.purple][index % 3] }]}>
                  <Text style={styles.testimonialAvatarText}>{testimonial.avatar}</Text>
                </View>
                <View>
                  <Text style={styles.testimonialName}>{testimonial.name}</Text>
                  <Text style={styles.testimonialRole}>{testimonial.role}, {testimonial.company}</Text>
                </View>
              </View>
            </View>
          ))}
        </View>
      </View>

      {/* Pricing Section */}
      <View 
        style={[styles.section, styles.sectionDark]}
        onLayout={(e) => handleSectionLayout('pricing', e.nativeEvent.layout.y)}
      >
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>PRICING</Text>
          <Text style={styles.sectionTitle}>Simple, Transparent Pricing</Text>
          <Text style={styles.sectionSubtitle}>
            No hidden fees. Cancel anytime. Start with a 14-day free trial.
          </Text>
        </View>
        
        <View style={styles.pricingGrid}>
          {/* Starter Plan */}
          <View style={styles.pricingCard}>
            <Text style={styles.pricingPlanName}>Starter</Text>
            <View style={styles.pricingPriceRow}>
              <Text style={styles.pricingPrice}>$49</Text>
              <Text style={styles.pricingPeriod}>/month</Text>
            </View>
            <Text style={styles.pricingDescription}>Perfect for individual sales reps</Text>
            <View style={styles.pricingFeatures}>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>500 SMS messages/month</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>1,000 Email sends/month</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>500 Contacts</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Basic analytics</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Digital business card</Text>
              </View>
            </View>
            <TouchableOpacity style={styles.pricingButton} onPress={handleGetStarted}>
              <Text style={styles.pricingButtonText}>Start Free Trial</Text>
            </TouchableOpacity>
          </View>
          
          {/* Professional Plan */}
          <View style={[styles.pricingCard, styles.pricingCardFeatured]}>
            <View style={styles.pricingBadge}>
              <Text style={styles.pricingBadgeText}>Most Popular</Text>
            </View>
            <Text style={styles.pricingPlanName}>Professional</Text>
            <View style={styles.pricingPriceRow}>
              <Text style={styles.pricingPrice}>$79</Text>
              <Text style={styles.pricingPeriod}>/month</Text>
            </View>
            <Text style={styles.pricingDescription}>For growing sales teams</Text>
            <View style={styles.pricingFeatures}>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>2,000 SMS messages/month</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>5,000 Email sends/month</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Unlimited contacts</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Advanced analytics</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Team collaboration</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Priority support</Text>
              </View>
            </View>
            <TouchableOpacity style={[styles.pricingButton, styles.pricingButtonFeatured]} onPress={handleGetStarted}>
              <Text style={styles.pricingButtonTextFeatured}>Start Free Trial</Text>
            </TouchableOpacity>
          </View>
          
          {/* Enterprise Plan */}
          <View style={styles.pricingCard}>
            <Text style={styles.pricingPlanName}>Enterprise</Text>
            <View style={styles.pricingPriceRow}>
              <Text style={styles.pricingPrice}>Custom</Text>
            </View>
            <Text style={styles.pricingDescription}>For large organizations</Text>
            <View style={styles.pricingFeatures}>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Unlimited messaging</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Unlimited contacts</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>White-label options</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Dedicated account manager</Text>
              </View>
              <View style={styles.pricingFeatureRow}>
                <Ionicons name="checkmark-circle" size={18} color={COLORS.green} />
                <Text style={styles.pricingFeatureText}>Custom integrations</Text>
              </View>
            </View>
            <TouchableOpacity style={styles.pricingButton} onPress={handleScheduleDemo}>
              <Text style={styles.pricingButtonText}>Contact Sales</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* FAQ Section */}
      <View 
        style={styles.section}
        onLayout={(e) => handleSectionLayout('faq', e.nativeEvent.layout.y)}
      >
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>FAQ</Text>
          <Text style={styles.sectionTitle}>Frequently Asked Questions</Text>
        </View>
        
        <View style={styles.faqContainer}>
          <View style={styles.faqItem}>
            <Text style={styles.faqQuestion}>How does the free trial work?</Text>
            <Text style={styles.faqAnswer}>
              Start with a 14-day free trial with full access to all Professional features. No credit card required. Cancel anytime.
            </Text>
          </View>
          
          <View style={styles.faqItem}>
            <Text style={styles.faqQuestion}>Can I import my existing contacts?</Text>
            <Text style={styles.faqAnswer}>
              Yes! Import contacts from your phone, spreadsheets (CSV/Excel), or sync from other CRMs like Salesforce, HubSpot, and more.
            </Text>
          </View>
          
          <View style={styles.faqItem}>
            <Text style={styles.faqQuestion}>Is my data secure?</Text>
            <Text style={styles.faqAnswer}>
              Absolutely. We use bank-level encryption, are SOC 2 compliant, and never sell your data. Your customer information is safe with us.
            </Text>
          </View>
          
          <View style={styles.faqItem}>
            <Text style={styles.faqQuestion}>Do I need a separate phone number for SMS?</Text>
            <Text style={styles.faqAnswer}>
              We provide you with a dedicated business phone number, or you can use your existing number with our Twilio integration.
            </Text>
          </View>
          
          <View style={styles.faqItem}>
            <Text style={styles.faqQuestion}>What kind of support do you offer?</Text>
            <Text style={styles.faqAnswer}>
              All plans include email support. Professional plans get priority support, and Enterprise customers have a dedicated account manager.
            </Text>
          </View>
        </View>
      </View>

      {/* CTA Section */}
      <View style={styles.ctaSection}>
        <View style={styles.ctaGlow} />
        <Text style={styles.ctaSectionTitle}>Ready to Transform Your Sales?</Text>
        <Text style={styles.ctaSectionSubtitle}>
          Join hundreds of teams already using iMOS to build stronger customer relationships.
        </Text>
        <View style={styles.ctaSectionButtons}>
          <TouchableOpacity style={styles.ctaButton} onPress={handleGetStarted}>
            <Text style={styles.ctaButtonText}>Get Started Free</Text>
            <Ionicons name="arrow-forward" size={20} color="#000" />
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={handleScheduleDemo}>
            <Text style={styles.secondaryButtonText}>Schedule Demo</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <View style={styles.footerContent}>
          <View style={styles.footerBrand}>
            <View style={styles.logoContainer}>
              <Image 
                source={{ uri: IMOS_LOGO }} 
                style={styles.footerLogo}
                resizeMode="contain"
              />
            </View>
            <Text style={styles.footerTagline}>Innovation Meets Old School</Text>
            <Text style={styles.footerDescription}>
              Empowering sales teams with the perfect blend of technology and timeless relationship-building.
            </Text>
          </View>
          
          <View style={styles.footerLinks}>
            <View style={styles.footerColumn}>
              <Text style={styles.footerColumnTitle}>Product</Text>
              <TouchableOpacity><Text style={styles.footerLink}>Features</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Pricing</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Integrations</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>API</Text></TouchableOpacity>
            </View>
            <View style={styles.footerColumn}>
              <Text style={styles.footerColumnTitle}>Company</Text>
              <TouchableOpacity><Text style={styles.footerLink}>About</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Blog</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Careers</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Contact</Text></TouchableOpacity>
            </View>
            <View style={styles.footerColumn}>
              <Text style={styles.footerColumnTitle}>Legal</Text>
              <TouchableOpacity onPress={() => router.push('/privacy')}><Text style={styles.footerLink}>Privacy</Text></TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/terms')}><Text style={styles.footerLink}>Terms</Text></TouchableOpacity>
              <TouchableOpacity><Text style={styles.footerLink}>Security</Text></TouchableOpacity>
            </View>
          </View>
        </View>
        
        <View style={styles.footerBottom}>
          <Text style={styles.footerCopyright}>© 2026 iMOS. All rights reserved.</Text>
          <View style={styles.footerSocials}>
            <TouchableOpacity style={styles.socialIcon}>
              <Ionicons name="logo-twitter" size={20} color={COLORS.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.socialIcon}>
              <Ionicons name="logo-linkedin" size={20} color={COLORS.textSecondary} />
            </TouchableOpacity>
            <TouchableOpacity style={styles.socialIcon}>
              <Ionicons name="logo-instagram" size={20} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </ScrollView>
    
    {/* Demo Request Modal */}
    <Modal
      visible={showDemoModal}
      transparent
      animationType="fade"
      onRequestClose={() => setShowDemoModal(false)}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <TouchableOpacity 
            style={styles.modalClose}
            onPress={() => setShowDemoModal(false)}
          >
            <Ionicons name="close" size={24} color={COLORS.textSecondary} />
          </TouchableOpacity>
          
          {submitSuccess ? (
            <View style={styles.successContainer}>
              <Ionicons name="checkmark-circle" size={64} color={COLORS.green} />
              <Text style={styles.successTitle}>Thank You!</Text>
              <Text style={styles.successText}>
                We've received your demo request. Our team will reach out to you within 24 hours to schedule a personalized demo.
              </Text>
              <TouchableOpacity 
                style={styles.ctaButton}
                onPress={() => setShowDemoModal(false)}
              >
                <Text style={styles.ctaButtonText}>Close</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <>
              <Text style={styles.modalTitle}>Schedule a Demo</Text>
              <Text style={styles.modalSubtitle}>
                See how iMOS can transform your sales process. Fill out the form and we'll be in touch within 24 hours.
              </Text>
              
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Full Name *</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="John Smith"
                  placeholderTextColor={COLORS.textTertiary}
                  value={demoForm.name}
                  onChangeText={(text) => setDemoForm(prev => ({ ...prev, name: text }))}
                />
              </View>
              
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Email *</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="john@company.com"
                  placeholderTextColor={COLORS.textTertiary}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  value={demoForm.email}
                  onChangeText={(text) => setDemoForm(prev => ({ ...prev, email: text }))}
                />
              </View>
              
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Phone *</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="(555) 123-4567"
                  placeholderTextColor={COLORS.textTertiary}
                  keyboardType="phone-pad"
                  value={demoForm.phone}
                  onChangeText={(text) => setDemoForm(prev => ({ ...prev, phone: text }))}
                />
              </View>
              
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Company</Text>
                <TextInput
                  style={styles.formInput}
                  placeholder="Your Company Name"
                  placeholderTextColor={COLORS.textTertiary}
                  value={demoForm.company}
                  onChangeText={(text) => setDemoForm(prev => ({ ...prev, company: text }))}
                />
              </View>
              
              <View style={styles.formGroup}>
                <Text style={styles.formLabel}>Message (Optional)</Text>
                <TextInput
                  style={[styles.formInput, styles.formTextarea]}
                  placeholder="Tell us about your sales team and goals..."
                  placeholderTextColor={COLORS.textTertiary}
                  multiline
                  numberOfLines={3}
                  value={demoForm.message}
                  onChangeText={(text) => setDemoForm(prev => ({ ...prev, message: text }))}
                />
              </View>
              
              <TouchableOpacity 
                style={[styles.ctaButton, styles.submitButton]}
                onPress={handleDemoSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <>
                    <Text style={styles.ctaButtonText}>Request Demo</Text>
                    <Ionicons name="arrow-forward" size={20} color="#000" />
                  </>
                )}
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>
    </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  content: {
    minHeight: '100%',
  },
  
  // Navigation
  nav: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    paddingTop: Platform.OS === 'web' ? 0 : 50,
    backgroundColor: 'transparent',
  },
  navContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 16,
    maxWidth: 1200,
    marginHorizontal: 'auto',
    width: '100%',
  },
  logoContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  navLogo: {
    width: 240,
    height: 80,
  },
  footerLogo: {
    width: 100,
    height: 36,
  },
  logoIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoText: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.textPrimary,
    letterSpacing: -0.5,
  },
  navLinks: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 32,
  },
  navLink: {
    paddingVertical: 8,
  },
  navLinkText: {
    fontSize: 15,
    color: COLORS.textSecondary,
    fontWeight: '500',
  },
  ctaButtonSmall: {
    backgroundColor: COLORS.accent,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  ctaButtonSmallText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#000',
  },
  
  // Hero
  hero: {
    paddingTop: 100,
    paddingBottom: 80,
    paddingHorizontal: 24,
    position: 'relative',
    overflow: 'hidden',
    backgroundColor: '#000000',
  },
  heroRow: {
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    maxWidth: 1200,
    marginHorizontal: 'auto',
    alignItems: 'center',
    gap: 60,
  },
  heroTextContent: {
    flex: 1,
    alignItems: Platform.OS === 'web' ? 'flex-start' : 'center',
  },
  heroGlow: {
    position: 'absolute',
    top: 100,
    left: '50%',
    width: 600,
    height: 600,
    backgroundColor: COLORS.accent,
    opacity: 0.1,
    borderRadius: 300,
    transform: [{ translateX: -300 }],
  },
  heroContent: {
    maxWidth: 800,
    marginHorizontal: 'auto',
    alignItems: 'center',
  },
  categoryBadge: {
    backgroundColor: 'rgba(0, 122, 255, 0.15)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginBottom: 20,
    alignSelf: Platform.OS === 'web' ? 'flex-start' : 'center',
  },
  categoryText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#007AFF',
    letterSpacing: 2,
  },
  taglineContainer: {
    marginBottom: 24,
  },
  taglineText: {
    fontSize: Platform.OS === 'web' ? 64 : 48,
    fontWeight: '800',
    letterSpacing: -2,
    textAlign: Platform.OS === 'web' ? 'left' : 'center',
  },
  taglineSubtext: {
    fontSize: Platform.OS === 'web' ? 28 : 22,
    fontWeight: '600',
    color: '#007AFF',
    textAlign: Platform.OS === 'web' ? 'left' : 'center',
    marginTop: 8,
  },
  taglineI: {
    color: '#FF3B30', // Red
  },
  taglineApostrophe: {
    color: '#34C759', // Green - same as School
  },
  taglineM: {
    color: '#007AFF', // Blue
  },
  taglineSpace: {
    color: '#FFFFFF',
  },
  taglineOld: {
    color: '#FFD60A', // Yellow
  },
  taglineSchool: {
    color: '#34C759', // Green
  },
  heroLogo: {
    width: Platform.OS === 'web' ? 280 : 200,
    height: Platform.OS === 'web' ? 280 : 200,
    marginBottom: 32,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: `${COLORS.accent}15`,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: `${COLORS.accent}30`,
    marginBottom: 24,
  },
  badgeText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.accent,
    letterSpacing: 0.5,
  },
  heroTitle: {
    fontSize: Platform.OS === 'web' ? 64 : 40,
    fontWeight: '800',
    color: COLORS.textPrimary,
    textAlign: 'center',
    lineHeight: Platform.OS === 'web' ? 72 : 48,
    letterSpacing: -2,
    marginBottom: 24,
  },
  heroTitleAccent: {
    color: COLORS.accent,
  },
  heroSubtitle: {
    fontSize: 18,
    color: COLORS.textSecondary,
    textAlign: Platform.OS === 'web' ? 'left' : 'center',
    lineHeight: 28,
    maxWidth: 500,
    marginBottom: 32,
  },
  heroButtons: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 40,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  ctaButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: COLORS.accent,
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
  },
  ctaButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
  secondaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: COLORS.elevated,
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  heroStats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 40,
  },
  heroStat: {
    alignItems: 'center',
  },
  heroStatNumber: {
    fontSize: 36,
    fontWeight: '800',
    color: COLORS.textPrimary,
    letterSpacing: -1,
  },
  heroStatLabel: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 4,
  },
  heroStatDivider: {
    width: 1,
    height: 40,
    backgroundColor: COLORS.border,
  },
  
  // Phone Mockup
  phoneContainer: {
    flex: Platform.OS === 'web' ? 0.8 : 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 40,
  },
  phoneMockup: {
    width: 280,
    height: 580,
    backgroundColor: '#F2F2F7',
    borderRadius: 44,
    padding: 0,
    borderWidth: 2,
    borderColor: '#E5E5EA',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.3,
    shadowRadius: 40,
    overflow: 'hidden',
  },
  phoneNotch: {
    width: 90,
    height: 24,
    backgroundColor: '#000',
    borderRadius: 12,
    alignSelf: 'center',
    marginTop: 10,
    marginBottom: 6,
  },
  phoneScreen: {
    flex: 1,
    backgroundColor: '#F2F2F7',
    overflow: 'hidden',
  },
  phoneHeader: {
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E5EA',
  },
  phoneHeaderText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#000000',
    textAlign: 'center',
  },
  messagesContainer: {
    flex: 1,
    padding: 16,
    gap: 12,
  },
  messageOutgoing: {
    alignSelf: 'flex-end',
    backgroundColor: '#007AFF',
    borderRadius: 18,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '85%',
  },
  messageOutgoingText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 20,
  },
  messageIncoming: {
    alignSelf: 'flex-start',
    backgroundColor: '#E5E5EA',
    borderRadius: 18,
    borderBottomLeftRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '85%',
  },
  messageIncomingText: {
    color: '#000000',
    fontSize: 14,
    lineHeight: 20,
  },
  messageTime: {
    fontSize: 10,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 4,
    textAlign: 'right',
  },
  messageTimeIncoming: {
    fontSize: 10,
    color: 'rgba(0,0,0,0.5)',
    marginTop: 4,
  },
  phoneHomeBar: {
    width: 100,
    height: 4,
    backgroundColor: '#333',
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 6,
    marginBottom: 8,
  },
  
  // Sections
  section: {
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  sectionDark: {
    backgroundColor: COLORS.surface,
  },
  sectionHeader: {
    alignItems: 'center',
    marginBottom: 60,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.accent,
    letterSpacing: 2,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: Platform.OS === 'web' ? 42 : 32,
    fontWeight: '800',
    color: COLORS.textPrimary,
    textAlign: 'center',
    letterSpacing: -1,
    marginBottom: 16,
  },
  sectionSubtitle: {
    fontSize: 16,
    color: COLORS.textSecondary,
    textAlign: 'center',
    maxWidth: 500,
    lineHeight: 24,
  },
  
  // Features
  featuresGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 24,
    maxWidth: 1200,
    marginHorizontal: 'auto',
    justifyContent: 'center',
  },
  featureCard: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    padding: 28,
    width: Platform.OS === 'web' ? 'calc(33.333% - 16px)' : '100%',
    minWidth: 280,
    maxWidth: 380,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  featureIcon: {
    width: 56,
    height: 56,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  featureTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 10,
  },
  featureDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 22,
  },
  
  // Steps
  stepsContainer: {
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
    maxWidth: 1000,
    marginHorizontal: 'auto',
  },
  step: {
    alignItems: 'center',
    flex: 1,
    maxWidth: 280,
  },
  stepNumber: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  stepNumberText: {
    fontSize: 20,
    fontWeight: '800',
    color: '#000',
  },
  stepTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 10,
    textAlign: 'center',
  },
  stepDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  stepConnector: {
    width: Platform.OS === 'web' ? 60 : 2,
    height: Platform.OS === 'web' ? 2 : 40,
    backgroundColor: COLORS.border,
  },
  
  // Testimonials
  testimonialsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 24,
    maxWidth: 1200,
    marginHorizontal: 'auto',
    justifyContent: 'center',
  },
  testimonialCard: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    padding: 28,
    width: Platform.OS === 'web' ? 'calc(33.333% - 16px)' : '100%',
    minWidth: 300,
    maxWidth: 400,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  testimonialStars: {
    flexDirection: 'row',
    gap: 4,
    marginBottom: 16,
  },
  testimonialQuote: {
    fontSize: 15,
    color: COLORS.textSecondary,
    lineHeight: 24,
    marginBottom: 20,
    fontStyle: 'italic',
  },
  testimonialAuthor: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  testimonialAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
  },
  testimonialAvatarText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  testimonialName: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  testimonialRole: {
    fontSize: 13,
    color: COLORS.textTertiary,
  },
  
  // Pricing
  pricingGrid: {
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    gap: 24,
    maxWidth: 1100,
    marginHorizontal: 'auto',
    justifyContent: 'center',
    alignItems: 'stretch',
  },
  pricingCard: {
    backgroundColor: COLORS.card,
    borderRadius: 20,
    padding: 32,
    flex: 1,
    minWidth: 280,
    maxWidth: 350,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  pricingCardFeatured: {
    borderColor: COLORS.accent,
    borderWidth: 2,
    position: 'relative',
  },
  pricingBadge: {
    position: 'absolute',
    top: -12,
    left: '50%',
    transform: [{ translateX: -50 }],
    backgroundColor: COLORS.accent,
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 20,
  },
  pricingBadgeText: {
    color: '#000',
    fontSize: 12,
    fontWeight: '700',
  },
  pricingPlanName: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  pricingPriceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 8,
  },
  pricingPrice: {
    fontSize: 42,
    fontWeight: '800',
    color: COLORS.textPrimary,
  },
  pricingPeriod: {
    fontSize: 16,
    color: COLORS.textSecondary,
    marginLeft: 4,
  },
  pricingDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginBottom: 24,
  },
  pricingFeatures: {
    gap: 12,
    marginBottom: 24,
  },
  pricingFeatureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  pricingFeatureText: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  pricingButton: {
    backgroundColor: COLORS.elevated,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  pricingButtonFeatured: {
    backgroundColor: COLORS.accent,
    borderColor: COLORS.accent,
  },
  pricingButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  pricingButtonTextFeatured: {
    fontSize: 15,
    fontWeight: '600',
    color: '#000',
  },
  
  // FAQ
  faqContainer: {
    maxWidth: 800,
    marginHorizontal: 'auto',
    gap: 16,
  },
  faqItem: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    padding: 24,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  faqQuestion: {
    fontSize: 17,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  faqAnswer: {
    fontSize: 15,
    color: COLORS.textSecondary,
    lineHeight: 24,
  },
  
  // CTA Section
  ctaSection: {
    paddingVertical: 100,
    paddingHorizontal: 24,
    alignItems: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  ctaGlow: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    width: 500,
    height: 500,
    backgroundColor: COLORS.accent,
    opacity: 0.08,
    borderRadius: 250,
    transform: [{ translateX: -250 }, { translateY: -250 }],
  },
  ctaSectionTitle: {
    fontSize: Platform.OS === 'web' ? 42 : 32,
    fontWeight: '800',
    color: COLORS.textPrimary,
    textAlign: 'center',
    letterSpacing: -1,
    marginBottom: 16,
  },
  ctaSectionSubtitle: {
    fontSize: 16,
    color: COLORS.textSecondary,
    textAlign: 'center',
    maxWidth: 500,
    lineHeight: 24,
    marginBottom: 40,
  },
  ctaSectionButtons: {
    flexDirection: 'row',
    gap: 16,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  
  // Footer
  footer: {
    backgroundColor: COLORS.surface,
    paddingTop: 60,
    paddingBottom: 30,
    paddingHorizontal: 24,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  footerContent: {
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    justifyContent: 'space-between',
    gap: 48,
    maxWidth: 1200,
    marginHorizontal: 'auto',
    marginBottom: 48,
  },
  footerBrand: {
    maxWidth: 300,
  },
  footerTagline: {
    fontSize: 14,
    color: COLORS.accent,
    fontWeight: '600',
    marginTop: 12,
    marginBottom: 12,
  },
  footerDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 22,
  },
  footerLinks: {
    flexDirection: 'row',
    gap: 48,
    flexWrap: 'wrap',
  },
  footerColumn: {
    minWidth: 120,
  },
  footerColumnTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 16,
  },
  footerLink: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginBottom: 12,
  },
  footerBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 24,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    maxWidth: 1200,
    marginHorizontal: 'auto',
  },
  footerCopyright: {
    fontSize: 13,
    color: COLORS.textTertiary,
  },
  footerSocials: {
    flexDirection: 'row',
    gap: 16,
  },
  socialIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.elevated,
    justifyContent: 'center',
    alignItems: 'center',
  },
  
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: COLORS.card,
    borderRadius: 20,
    padding: 32,
    width: '100%',
    maxWidth: 480,
    maxHeight: '90%',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  modalClose: {
    position: 'absolute',
    top: 16,
    right: 16,
    zIndex: 10,
    padding: 8,
  },
  modalTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  modalSubtitle: {
    fontSize: 15,
    color: COLORS.textSecondary,
    marginBottom: 24,
    lineHeight: 22,
  },
  formGroup: {
    marginBottom: 16,
  },
  formLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  formInput: {
    backgroundColor: COLORS.elevated,
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  formTextarea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  submitButton: {
    marginTop: 8,
    width: '100%',
  },
  successContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginTop: 16,
    marginBottom: 12,
  },
  successText: {
    fontSize: 16,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 24,
  },
});
