import unittest
import redis

class TestTuiternot(unittest.TestCase):
    
    def setUp(self):
        # Conexión a Redis
        self.r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        # Limpieza de llaves de prueba
        self.r.delete('user:shinoon', 'tweets:shinoon', 'following:shinoon')

    def test_user_creation(self):
        self.r.hset('user:shinoon', mapping={'username': 'shinoon', 'email': 'shinoon@mail.cl'})
        data = self.r.hgetall('user:shinoon')
        self.assertEqual(data['username'], 'shinoon')


    def test_tweet_publication(self):
        self.r.lpush('tweets:shinoon', "Tercer tweet muerte a los que usan incineroar")
        last_tweet = self.r.lindex('tweets:shinoon', 0)
        self.assertEqual(last_tweet, "Tercer tweet muerte a los que usan incineroar")

    def test_following_logic(self):
        self.r.sadd('following:shinoon', 'amigo1')
        self.r.sadd('following:shinoon', 'amigo1') 
        self.assertEqual(self.r.scard('following:shinoon'), 1)

    def test_feed_seguidos(self):
        # 1. Shinoon sigue a 'anshyn'
        self.r.sadd('following:shinoon', 'anshyn')
        
        # 2. 'anshyn' publica un tweet
        tweet_amigo = "¡Nuevo post de anshyn!"
        self.r.lpush('tweets:anshyn', tweet_amigo)
        
        # 3. Simulamos obtener el feed: 
        # Buscamos a quién sigue shinoon y traemos sus tweets
        seguidos = self.r.smembers('following:shinoon')
        feed = []
        for amigo in seguidos:
            tweets = self.r.lrange(f'tweets:{amigo}', 0, 0) # Trae solo el último
            feed.extend(tweets)
            
        # 4. Verificamos que el tweet del amigo esté en el feed de Shinoon
        self.assertIn(tweet_amigo, feed)
        
        # Limpieza extra para este test
        self.r.delete('tweets:anshyn')

if __name__ == '__main__':
    unittest.main()