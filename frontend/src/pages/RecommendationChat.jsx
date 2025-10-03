// pages/TripChat.jsx

import { ArrowLeft, Checkmark, Reset, Send } from '@carbon/icons-react';
import {
  Button,
  ClickableTile,
  Column,
  FlexGrid,
  Grid,
  InlineLoading,
  Layer,
  ProgressIndicator,
  ProgressStep,
  Row,
  SkeletonText,
  Stack,
  Tag,
  TextArea,
  Tile,
  ToastNotification,
} from '@carbon/react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

const RecommendationChat = () => {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  
  // State
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [currentStage, setCurrentStage] = useState('initial');
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [destinations, setDestinations] = useState(null);
  const [error, setError] = useState(null);
  const [tripTitle, setTripTitle] = useState('Your Trip');

  // Scroll to bottom when messages update
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversation history on mount
  useEffect(() => {
    loadConversation();
  }, [tripId]);

  const loadConversation = async () => {
    try {
      setIsLoadingHistory(true);
      const response = await api.get(`/destination_search/conversations/${tripId}/`);
      
      if (response.data.messages) {
        setMessages(response.data.messages);
        setTripTitle(response.data.trip_title || 'Your Trip');
        
        if (response.data.state) {
          setCurrentStage(response.data.state.current_stage);
          setProgress({
            current: response.data.state.questions_asked,
            total: response.data.state.total_questions
          });
        }
        
        if (response.data.destinations) {
          setDestinations(response.data.destinations);
        }
      }
    } catch (err) {
      if (err.response?.status === 404) {
        // No conversation yet, that's okay
        console.log('No conversation started yet');
      } else {
        setError('Failed to load conversation history');
      }
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setError(null);

    // Add user message immediately for better UX
    const tempUserMessage = {
      id: `temp-${Date.now()}`,
      is_user: true,
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMessage]);

    try {
      const response = await api.post('/destination_search/chat/', {
        trip_id: parseInt(tripId),
        message: userMessage
      });

      // Remove temp message and add real ones
      const userMsg = { ...response.data.user_message, is_user: true };
      const aiMsg   = { ...response.data.ai_message,   is_user: false };

      setMessages(prev => [
        ...prev.filter(msg => msg.id !== tempUserMessage.id),
        userMsg,
        aiMsg,
      ]);

      // Update stage and progress
      if (response.data.stage) {
        setCurrentStage(response.data.stage);
      }
      
      if (response.data.progress !== undefined) {
        setProgress({
          current: response.data.metadata?.question_number || 0,
          total: response.data.metadata?.total_questions || 0
        });
      }

      // Update destinations if provided
      if (response.data.destinations) {
        setDestinations(response.data.destinations);
      }

      // Check if destination was selected
      if (response.data.metadata?.trip_status === 'destinations_selected') {
        // Show success and redirect after delay
        setTimeout(() => {
          navigate('/');
        }, 3000);
      }

    } catch (err) {
      // Remove temp message on error
      setMessages(prev => prev.filter(msg => msg.id !== tempUserMessage.id));
      setError(err.response?.data?.error || 'Failed to send message');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const selectDestination = (destination) => {
    setInputValue(`Let's go with ${destination.name}!`);
    // Auto-send after a moment for smooth UX
    setTimeout(() => sendMessage(), 100);
  };

  const resetConversation = async () => {
    if (window.confirm('Are you sure you want to start over? This will clear all your preferences.')) {
      try {
        await api.post(`/destination_search/conversations/${tripId}/reset/`);
        setMessages([]);
        setDestinations(null);
        setCurrentStage('initial');
        setProgress({ current: 0, total: 0 });
        setError(null);
      } catch (err) {
        setError('Failed to reset conversation');
      }
    }
  };

  const getStageLabel = () => {
    switch (currentStage) {
      case 'initial':
        return 'Getting Started';
      case 'asking_clarifications':
        return `Question ${progress.current} of ${progress.total}`;
      case 'generating_destinations':
        return 'Finding Perfect Destinations...';
      case 'destinations_complete':
        return 'Choose Your Destination';
      case 'commitment_detected':
        return 'Destination Selected!';
      default:
        return 'Planning Your Trip';
    }
  };

  const getProgressSteps = () => {
    const steps = [
      { label: 'Share Preferences', status: currentStage !== 'initial' ? 'complete' : 'current' },
      { label: 'Answer Questions', status: currentStage === 'asking_clarifications' ? 'current' : 
                                           currentStage === 'initial' ? 'incomplete' : 'complete' },
      { label: 'Review Destinations', status: currentStage === 'destinations_complete' ? 'current' :
                                              currentStage === 'commitment_detected' ? 'complete' : 'incomplete' },
      { label: 'Select Destination', status: currentStage === 'commitment_detected' ? 'complete' : 'incomplete' }
    ];
    return steps;
  };

  if (isLoadingHistory) {
    return (
      <FlexGrid fullWidth>
        <Row>
          <Column>
            <Layer>
              <Stack gap={6}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Button
                    kind="ghost"
                    size="sm"
                    renderIcon={ArrowLeft}
                    onClick={() => navigate('/')}
                  >
                    Back
                  </Button>
                  <h2>Loading conversation...</h2>
                </div>
                <SkeletonText paragraph lineCount={4} />
              </Stack>
            </Layer>
          </Column>
        </Row>
      </FlexGrid>
    );
  }

  return (
    <FlexGrid fullWidth style={{ minHeight: '100vh', padding: 0 }}>
      <Row>
        <Column>
          <Stack gap={0}>
            {/* Header */}
            <Layer style={{ padding: '1rem', borderBottom: '1px solid #e0e0e0' }}>
              <Stack gap={5}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Button
                    kind="ghost"
                    size="sm"
                    renderIcon={ArrowLeft}
                    onClick={() => navigate('/')}
                  >
                    Back
                  </Button>
                  <h2 style={{ margin: 0 }}>{tripTitle} - Destination Discovery</h2>
                  <Button
                    kind="ghost"
                    size="sm"
                    renderIcon={Reset}
                    onClick={resetConversation}
                  >
                    Start Over
                  </Button>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <ProgressIndicator 
                    currentIndex={getProgressSteps().findIndex(s => s.status === 'current')}
                    spaceEqually
                    style={{ flex: 1 }}
                  >
                    {getProgressSteps().map((step, index) => (
                      <ProgressStep
                        key={index}
                        label={step.label}
                        complete={step.status === 'complete'}
                        current={step.status === 'current'}
                      />
                    ))}
                  </ProgressIndicator>
                  <Tag type="blue" size="md">
                    {getStageLabel()}
                  </Tag>
                </div>
              </Stack>
            </Layer>

            {/* Messages Area */}
            <div style={{ 
              flex: 1, 
              overflowY: 'auto', 
              padding: '1.5rem',
              minHeight: 'calc(100vh - 300px)',
              maxHeight: 'calc(100vh - 300px)'
            }}>
              {messages.length === 0 && (
                <Layer>
                  <Tile style={{ textAlign: 'center', maxWidth: '600px', margin: '2rem auto' }}>
                    <h3>Welcome to Your Trip Planning Journey! 🌍</h3>
                    <p style={{ margin: '1rem 0' }}>
                      Tell me about your dream vacation. What kind of experience are you looking for?
                    </p>
                    <Stack gap={3} orientation="horizontal" style={{ justifyContent: 'center' }}>
                      <Button
                        kind="tertiary"
                        size="sm"
                        onClick={() => setInputValue("I want a relaxing beach vacation with great food")}
                      >
                        Beach & Relaxation
                      </Button>
                      <Button
                        kind="tertiary"
                        size="sm"
                        onClick={() => setInputValue("I'm looking for adventure and outdoor activities")}
                      >
                        Adventure & Nature
                      </Button>
                      <Button
                        kind="tertiary"
                        size="sm"
                        onClick={() => setInputValue("I want to explore culture and history")}
                      >
                        Culture & History
                      </Button>
                    </Stack>
                  </Tile>
                </Layer>
              )}
              
              <Stack gap={4}>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    style={{
                      display: 'flex',
                      justifyContent: message.is_user ? 'flex-end' : 'flex-start',
                      marginBottom: '0.75rem',
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '70%',
                        backgroundColor: message.is_user ? '#0f62fe' : '#f4f4f4',
                        color: message.is_user ? 'white' : 'black',
                        padding: '0.75rem 1rem',
                        borderRadius: message.is_user
                          ? '16px 16px 0 16px'
                          : '16px 16px 16px 0', // bubble shape
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                      }}
                    >
                      <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
                      <div
                        style={{
                          fontSize: '0.7rem',
                          marginTop: '0.4rem',
                          textAlign: message.is_user ? 'right' : 'left',
                          opacity: 0.7,
                        }}
                      >
                        {new Date(message.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </div>
                  </div>
                ))}
                
                {isLoading && (
                  <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                    <Layer>
                      <Tile style={{ backgroundColor: '#f4f4f4' }}>
                        <InlineLoading description="AI is thinking..." />
                      </Tile>
                    </Layer>
                  </div>
                )}
              </Stack>
              
              <div ref={messagesEndRef} />
            </div>

            {/* Destinations Display */}
            {destinations && currentStage === 'destinations_complete' && (
              <Layer style={{ padding: '1rem', borderTop: '1px solid #e0e0e0' }}>
                <Stack gap={4}>
                  <h3>Your Personalized Destinations</h3>
                  <Grid narrow>
                    {destinations.map((dest, index) => (
                      <Column key={index} sm={4} md={4} lg={4}>
                        <ClickableTile
                          onClick={() => selectDestination(dest)}
                          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
                        >
                          <Stack gap={3}>
                            <h4>{dest.name}</h4>
                            {dest.country && (
                              <Tag type="blue" size="sm">{dest.country}</Tag>
                            )}
                            {dest.description && (
                              <p style={{ fontSize: '0.875rem', flex: 1 }}>
                                {dest.description}
                              </p>
                            )}
                            <Button
                              kind="primary"
                              size="sm"
                              renderIcon={Checkmark}
                              onClick={(e) => {
                                e.stopPropagation();
                                selectDestination(dest);
                              }}
                            >
                              Choose This
                            </Button>
                          </Stack>
                        </ClickableTile>
                      </Column>
                    ))}
                  </Grid>
                </Stack>
              </Layer>
            )}

            {/* Input Area */}
            <Layer style={{ padding: '1rem', borderTop: '1px solid #e0e0e0' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
                <TextArea
                  labelText=""
                  placeholder={
                    currentStage === 'initial' 
                      ? "Describe your ideal vacation..."
                      : currentStage === 'asking_clarifications'
                      ? "Type your answer..."
                      : "Ask about the destinations or make your choice..."
                  }
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  disabled={isLoading || currentStage === 'commitment_detected'}
                  rows={2}
                  style={{ flex: 1 }}
                />
                <Button
                  kind="primary"
                  renderIcon={Send}
                  iconDescription="Send message"
                  hasIconOnly
                  onClick={sendMessage}
                  disabled={!inputValue.trim() || isLoading || currentStage === 'commitment_detected'}
                />
              </div>
            </Layer>
          </Stack>
        </Column>
      </Row>

      {/* Toast Notifications */}
      {error && (
        <ToastNotification
          kind="error"
          title="Error"
          subtitle={error}
          timeout={5000}
          onClose={() => setError(null)}
          style={{ position: 'fixed', bottom: 20, right: 20, minWidth: 300, zIndex: 9999 }}
        />
      )}
      
      {currentStage === 'commitment_detected' && (
        <ToastNotification
          kind="success"
          title="Destination Selected!"
          subtitle="Redirecting to trip dashboard..."
          timeout={3000}
          style={{ position: 'fixed', bottom: 20, right: 20, minWidth: 300, zIndex: 9999 }}
        />
      )}
    </FlexGrid>
  );
};

export default RecommendationChat;