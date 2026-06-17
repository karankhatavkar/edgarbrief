import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { useSession } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

type Mode = 'signin' | 'signup'

export default function AuthPage() {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const navigate = useNavigate()
  const { session, loading: sessionLoading } = useSession()

  function switchMode(next: string) {
    setMode(next as Mode)
    setError(null)
    setSuccess(false)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (loading) return
    setError(null)
    setLoading(true)

    try {
      if (mode === 'signin') {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        navigate('/')
      } else {
        const { data, error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        // With email confirmation disabled, signUp returns a live session and
        // we drop the user straight into the app. Otherwise prompt them to
        // confirm via the emailed link.
        if (data.session) {
          navigate('/')
        } else {
          setSuccess(true)
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  if (!sessionLoading && session) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="font-heading text-2xl">EdgarBrief</CardTitle>
          <CardDescription>SEC filings, distilled.</CardDescription>
        </CardHeader>

        <CardContent>
          {success ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <p className="text-base font-medium">Check your inbox</p>
              <p className="text-sm text-muted-foreground">
                A confirmation link was sent to <strong>{email}</strong>.
              </p>
              <Button variant="ghost" onClick={() => switchMode('signin')}>
                Back to sign in
              </Button>
            </div>
          ) : (
            <Tabs value={mode} onValueChange={switchMode} className="gap-6">
              <TabsList className="w-full">
                <TabsTrigger value="signin">Sign in</TabsTrigger>
                <TabsTrigger value="signup">Create account</TabsTrigger>
              </TabsList>

              <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="email">Email address</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                    required
                  />
                </div>

                {error && (
                  <p role="alert" className="text-sm text-destructive">
                    {error}
                  </p>
                )}

                <Button type="submit" disabled={loading} className="w-full">
                  {loading
                    ? 'Please wait…'
                    : mode === 'signin'
                      ? 'Sign in'
                      : 'Create account'}
                </Button>
              </form>
            </Tabs>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
