import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  MessageSquare,
  Mail,
  Users,
  BarChart3,
  Smartphone,
  Shield,
  Zap,
  Star,
  CheckCircle,
  ArrowRight,
  Play,
  Menu,
  X,
  ChevronDown,
  Quote,
  Building2,
  Target,
  TrendingUp,
  Clock,
  Heart,
  Award,
  Globe,
  Phone,
  MapPin,
  Linkedin,
  Twitter,
  Instagram,
  Facebook,
} from 'lucide-react';
import './App.css';

// Navigation Component
const Navigation = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <nav className={`nav ${isScrolled ? 'nav-scrolled' : ''}`}>
      <div className="nav-container">
        <a href="#" className="logo">
          <span className="logo-i">i</span>
          <span className="logo-m">M</span>
          <span className="logo-o">O</span>
          <span className="logo-s">s</span>
        </a>
        
        <div className={`nav-links ${mobileMenuOpen ? 'nav-links-open' : ''}`}>
          <a href="#features">Features</a>
          <a href="#how-it-works">How It Works</a>
          <a href="#pricing">Pricing</a>
          <a href="#testimonials">Testimonials</a>
          <a href="#faq">FAQ</a>
        </div>
        
        <div className="nav-buttons">
          <a href="https://app.imosapp.com" className="btn btn-ghost">Sign In</a>
          <a href="https://app.imosapp.com/auth/signup" className="btn btn-primary">
            Get Started <ArrowRight size={16} />
          </a>
        </div>
        
        <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>
    </nav>
  );
};

// Hero Section
const Hero = () => (
  <section className="hero">
    <div className="hero-bg">
      <div className="hero-gradient" />
      <div className="hero-grid" />
    </div>
    
    <div className="hero-content">
      <h1 className="hero-title">
        <span className="hero-logo">
          <span className="hero-i">i</span>
          <span className="hero-m">M</span>
          <span className="hero-o">O</span>
          <span className="hero-s">s</span>
        </span>
      </h1>
      
      <h2 className="hero-tagline">
        <span className="tagline-white">Innovation</span>{' '}
        <span className="tagline-blue">Meets</span>{' '}
        <span className="tagline-purple">Old School</span>
      </h2>
      
      <p className="hero-subtitle">
        Built on timeless relationship principles and powered by modern automation, 
        this platform ensures every customer feels remembered. The system handles 
        the consistency... so you can focus on authentic human connection without 
        anyone falling through the cracks.
      </p>
      
      <div className="hero-buttons">
        <a href="https://app.imosapp.com/auth/signup" className="btn btn-primary btn-lg">
          Start Free Trial <ArrowRight size={18} />
        </a>
        <button className="btn btn-outline btn-lg">
          <Play size={18} /> Watch Demo
        </button>
      </div>
      
      <div className="hero-stats">
        <div className="hero-stat">
          <span className="hero-stat-value">10,000+</span>
          <span className="hero-stat-label">Active Users</span>
        </div>
        <div className="hero-stat-divider" />
        <div className="hero-stat">
          <span className="hero-stat-value">5M+</span>
          <span className="hero-stat-label">Messages Sent</span>
        </div>
        <div className="hero-stat-divider" />
        <div className="hero-stat">
          <span className="hero-stat-value">98%</span>
          <span className="hero-stat-label">Satisfaction Rate</span>
        </div>
      </div>
    </div>
    
    <div className="hero-image">
      <div className="phone-mockup">
        <div className="phone-screen">
          <div className="app-header">
            <span className="app-title">Inbox</span>
            <div className="app-toggle">
              <span className="toggle-active">SMS</span>
              <span>Email</span>
            </div>
          </div>
          <div className="app-content">
            <div className="message-preview">
              <div className="avatar" style={{background: '#007AFF'}}>JD</div>
              <div className="message-info">
                <span className="message-name">John Doe</span>
                <span className="message-text">Thanks for the follow up!</span>
              </div>
              <span className="message-time">2m</span>
            </div>
            <div className="message-preview">
              <div className="avatar" style={{background: '#34C759'}}>SM</div>
              <div className="message-info">
                <span className="message-name">Sarah Miller</span>
                <span className="message-text">I'm interested in the offer</span>
              </div>
              <span className="message-time">15m</span>
            </div>
            <div className="message-preview">
              <div className="avatar" style={{background: '#FF9500'}}>RJ</div>
              <div className="message-info">
                <span className="message-name">Robert Johnson</span>
                <span className="message-text">Can we schedule a call?</span>
              </div>
              <span className="message-time">1h</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
);

// Features Section
const features = [
  {
    icon: MessageSquare,
    color: '#007AFF',
    title: 'SMS Messaging',
    description: 'Send personalized text messages to your contacts instantly. Track delivery and responses in real-time.',
  },
  {
    icon: Mail,
    color: '#34C759',
    title: 'Email Campaigns',
    description: 'Create beautiful, branded email campaigns with our drag-and-drop editor and analytics dashboard.',
  },
  {
    icon: Users,
    color: '#FF9500',
    title: 'Contact Management',
    description: 'Organize your contacts with tags, notes, and custom fields. Import from any source.',
  },
  {
    icon: BarChart3,
    color: '#AF52DE',
    title: 'Analytics & Insights',
    description: 'Track open rates, click rates, and engagement metrics to optimize your outreach.',
  },
  {
    icon: Smartphone,
    color: '#FF2D55',
    title: 'Digital Business Cards',
    description: 'Share your contact info instantly with a beautiful, customizable digital card.',
  },
  {
    icon: Zap,
    color: '#FFD60A',
    title: 'Automation',
    description: 'Set up automated follow-ups, birthday messages, and nurture campaigns.',
  },
];

const Features = () => (
  <section id="features" className="features">
    <div className="container">
      <div className="section-header">
        <span className="section-badge">Features</span>
        <h2 className="section-title">Everything you need to <span className="gradient-text">close more deals</span></h2>
        <p className="section-subtitle">
          Powerful tools designed for modern sales professionals who value authentic connections.
        </p>
      </div>
      
      <div className="features-grid">
        {features.map((feature, index) => (
          <div key={index} className="feature-card">
            <div className="feature-icon" style={{ background: `${feature.color}15`, color: feature.color }}>
              <feature.icon size={24} />
            </div>
            <h3 className="feature-title">{feature.title}</h3>
            <p className="feature-description">{feature.description}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// How It Works Section
const steps = [
  {
    number: '01',
    title: 'Sign Up in Seconds',
    description: 'Create your account and import your contacts from your phone, spreadsheet, or other CRM.',
    color: '#007AFF',
  },
  {
    number: '02',
    title: 'Personalize Your Outreach',
    description: 'Use templates or create custom messages. Add your brand kit for professional emails.',
    color: '#34C759',
  },
  {
    number: '03',
    title: 'Connect & Convert',
    description: 'Send messages via SMS or email. Track responses and close more deals.',
    color: '#FF9500',
  },
];

const HowItWorks = () => (
  <section id="how-it-works" className="how-it-works">
    <div className="container">
      <div className="section-header">
        <span className="section-badge">How It Works</span>
        <h2 className="section-title">Get started in <span className="gradient-text">three simple steps</span></h2>
      </div>
      
      <div className="steps-container">
        {steps.map((step, index) => (
          <div key={index} className="step-card">
            <div className="step-number" style={{ color: step.color }}>{step.number}</div>
            <h3 className="step-title">{step.title}</h3>
            <p className="step-description">{step.description}</p>
            {index < steps.length - 1 && <div className="step-connector" />}
          </div>
        ))}
      </div>
    </div>
  </section>
);

// Pricing Section
const plans = [
  {
    name: 'Starter',
    price: '29',
    description: 'Perfect for individual sales reps',
    features: [
      '500 SMS messages/month',
      '1,000 Email sends/month',
      '500 Contacts',
      'Basic analytics',
      'Digital business card',
      'Email support',
    ],
    popular: false,
  },
  {
    name: 'Professional',
    price: '79',
    description: 'For growing sales teams',
    features: [
      '2,000 SMS messages/month',
      '5,000 Email sends/month',
      'Unlimited contacts',
      'Advanced analytics',
      'Custom brand kit',
      'Priority support',
      'Team collaboration',
      'API access',
    ],
    popular: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'For large organizations',
    features: [
      'Unlimited messaging',
      'Unlimited contacts',
      'White-label options',
      'Dedicated account manager',
      'Custom integrations',
      'SLA guarantee',
      'On-premise deployment',
      '24/7 phone support',
    ],
    popular: false,
  },
];

const Pricing = () => (
  <section id="pricing" className="pricing">
    <div className="container">
      <div className="section-header">
        <span className="section-badge">Pricing</span>
        <h2 className="section-title">Simple, transparent <span className="gradient-text">pricing</span></h2>
        <p className="section-subtitle">No hidden fees. Cancel anytime. Start with a 14-day free trial.</p>
      </div>
      
      <div className="pricing-grid">
        {plans.map((plan, index) => (
          <div key={index} className={`pricing-card ${plan.popular ? 'pricing-card-popular' : ''}`}>
            {plan.popular && <div className="popular-badge">Most Popular</div>}
            <h3 className="pricing-name">{plan.name}</h3>
            <div className="pricing-price">
              {plan.price !== 'Custom' && <span className="price-currency">$</span>}
              <span className="price-amount">{plan.price}</span>
              {plan.price !== 'Custom' && <span className="price-period">/month</span>}
            </div>
            <p className="pricing-description">{plan.description}</p>
            <ul className="pricing-features">
              {plan.features.map((feature, i) => (
                <li key={i}>
                  <CheckCircle size={16} className="check-icon" />
                  {feature}
                </li>
              ))}
            </ul>
            <button className={`btn ${plan.popular ? 'btn-primary' : 'btn-outline'} btn-full`}>
              {plan.price === 'Custom' ? 'Contact Sales' : 'Start Free Trial'}
            </button>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// Testimonials Section
const testimonials = [
  {
    quote: "iMos has completely transformed how I follow up with leads. My close rate has increased by 40% since I started using it.",
    author: "Michael Chen",
    role: "Sales Director",
    company: "AutoMax Dealership",
    avatar: "MC",
    color: '#007AFF',
  },
  {
    quote: "The SMS and email integration is seamless. I can reach my customers wherever they prefer, and the analytics help me optimize my approach.",
    author: "Jessica Martinez",
    role: "Senior Sales Rep",
    company: "Premier Motors",
    avatar: "JM",
    color: '#34C759',
  },
  {
    quote: "Finally, a CRM that understands the car business. The digital business card feature alone has generated dozens of referrals.",
    author: "David Thompson",
    role: "General Manager",
    company: "Thompson Auto Group",
    avatar: "DT",
    color: '#FF9500',
  },
];

const Testimonials = () => (
  <section id="testimonials" className="testimonials">
    <div className="container">
      <div className="section-header">
        <span className="section-badge">Testimonials</span>
        <h2 className="section-title">Loved by <span className="gradient-text">sales professionals</span></h2>
        <p className="section-subtitle">See what our customers have to say about iMos.</p>
      </div>
      
      <div className="testimonials-grid">
        {testimonials.map((testimonial, index) => (
          <div key={index} className="testimonial-card">
            <Quote className="quote-icon" size={32} />
            <p className="testimonial-quote">{testimonial.quote}</p>
            <div className="testimonial-author">
              <div className="testimonial-avatar" style={{ background: testimonial.color }}>
                {testimonial.avatar}
              </div>
              <div className="testimonial-info">
                <span className="testimonial-name">{testimonial.author}</span>
                <span className="testimonial-role">{testimonial.role}, {testimonial.company}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="testimonials-logos">
        <p className="logos-title">Trusted by leading dealerships nationwide</p>
        <div className="logos-grid">
          {['AutoMax', 'Premier Motors', 'Thompson Auto', 'Elite Cars', 'Victory Honda'].map((name, i) => (
            <div key={i} className="logo-placeholder">
              <Building2 size={24} />
              <span>{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  </section>
);

// FAQ Section
const faqs = [
  {
    question: 'How does the free trial work?',
    answer: 'Start with a 14-day free trial with full access to all Professional features. No credit card required. Cancel anytime.',
  },
  {
    question: 'Can I import my existing contacts?',
    answer: 'Yes! Import contacts from your phone, spreadsheets (CSV/Excel), or sync from other CRMs like Salesforce, HubSpot, and more.',
  },
  {
    question: 'Is my data secure?',
    answer: 'Absolutely. We use bank-level encryption, are SOC 2 compliant, and never sell your data. Your customer information is safe with us.',
  },
  {
    question: 'Do I need a separate phone number for SMS?',
    answer: 'We provide you with a dedicated business phone number, or you can use your existing number with our Twilio integration.',
  },
  {
    question: 'Can I customize email templates with my branding?',
    answer: 'Yes! Our Brand Kit feature lets you add your logo, colors, and company info to all outgoing emails.',
  },
  {
    question: 'What kind of support do you offer?',
    answer: 'All plans include email support. Professional plans get priority support, and Enterprise customers have a dedicated account manager.',
  },
];

const FAQ = () => {
  const [openIndex, setOpenIndex] = useState(null);
  
  return (
    <section id="faq" className="faq">
      <div className="container">
        <div className="section-header">
          <span className="section-badge">FAQ</span>
          <h2 className="section-title">Frequently asked <span className="gradient-text">questions</span></h2>
        </div>
        
        <div className="faq-list">
          {faqs.map((faq, index) => (
            <div 
              key={index} 
              className={`faq-item ${openIndex === index ? 'faq-item-open' : ''}`}
              onClick={() => setOpenIndex(openIndex === index ? null : index)}
            >
              <div className="faq-question">
                <span>{faq.question}</span>
                <ChevronDown className="faq-chevron" size={20} />
              </div>
              <div className="faq-answer">
                <p>{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// CTA Section
const CTA = () => (
  <section className="cta">
    <div className="container">
      <div className="cta-content">
        <div className="cta-icon">
          <Sparkles size={32} />
        </div>
        <h2 className="cta-title">Ready to transform your sales?</h2>
        <p className="cta-subtitle">
          Join thousands of sales professionals who are closing more deals with iMos.
        </p>
        <div className="cta-buttons">
          <a href="https://app.imosapp.com/auth/signup" className="btn btn-white btn-lg">
            Start Your Free Trial <ArrowRight size={18} />
          </a>
          <a href="#" className="btn btn-ghost-white btn-lg">
            Schedule a Demo
          </a>
        </div>
        <p className="cta-note">No credit card required. 14-day free trial.</p>
      </div>
    </div>
  </section>
);

// Footer
const Footer = () => (
  <footer className="footer">
    <div className="container">
      <div className="footer-grid">
        <div className="footer-brand">
          <a href="#" className="logo footer-logo">
            <span className="logo-i">i</span>
            <span className="logo-m">M</span>
            <span className="logo-o">O</span>
            <span className="logo-s">s</span>
          </a>
          <p className="footer-tagline">Innovation meets old school</p>
          <p className="footer-description">
            The modern CRM platform for sales professionals who value authentic connections.
          </p>
          <div className="footer-social">
            <a href="#" aria-label="Twitter"><Twitter size={20} /></a>
            <a href="#" aria-label="LinkedIn"><Linkedin size={20} /></a>
            <a href="#" aria-label="Instagram"><Instagram size={20} /></a>
            <a href="#" aria-label="Facebook"><Facebook size={20} /></a>
          </div>
        </div>
        
        <div className="footer-links">
          <h4>Product</h4>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <a href="#">Integrations</a>
          <a href="#">API</a>
          <a href="#">Changelog</a>
        </div>
        
        <div className="footer-links">
          <h4>Company</h4>
          <a href="#">About Us</a>
          <a href="#">Careers</a>
          <a href="#">Blog</a>
          <a href="#">Press</a>
          <a href="#">Contact</a>
        </div>
        
        <div className="footer-links">
          <h4>Resources</h4>
          <a href="#">Help Center</a>
          <a href="#">Documentation</a>
          <a href="#">Webinars</a>
          <a href="#">Community</a>
          <a href="#">Status</a>
        </div>
        
        <div className="footer-links">
          <h4>Legal</h4>
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Cookie Policy</a>
          <a href="#">GDPR</a>
        </div>
      </div>
      
      <div className="footer-bottom">
        <p>&copy; 2024 iMos. All rights reserved.</p>
        <div className="footer-contact">
          <span><MapPin size={14} /> San Francisco, CA</span>
          <span><Phone size={14} /> (555) 123-4567</span>
          <span><Mail size={14} /> hello@imosapp.com</span>
        </div>
      </div>
    </div>
  </footer>
);

// Main App
function App() {
  return (
    <div className="app">
      <Navigation />
      <Hero />
      <Features />
      <HowItWorks />
      <Pricing />
      <Testimonials />
      <FAQ />
      <CTA />
      <Footer />
    </div>
  );
}

export default App;
