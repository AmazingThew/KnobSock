using System;
using System.Net.Sockets;
using System.Threading;

public class Knobs
{
    private static int size;
    public static int[] knobs;

    private static Socket sock;

    private static Thread worker;
    private static bool running = false;

    public static void Start(int numKnobs)
    {
        if (!running)
        {
            size = numKnobs;
            knobs = new int[size];

            try
            {
                sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                sock.Connect("localhost", 8008);

                worker = new Thread(new ThreadStart(readFromServer));
                worker.Start();

                running = true;
            }
            catch (SocketException e)
            {
                Console.WriteLine(e);
            }
        }
    }

    public static void Stop()
    {
        if (running)
        {
            sock.Shutdown(SocketShutdown.Both);
            sock.Close();
            running = false;
        }
    }

    public static float Get(int index)
    {
        return get(index, 0, 1);
    }

    public static float Get(int index, float max)
    {
        return get(index, 0, max);
    }

    public static float Get(int index, float min, float max)
    {
        float value = (float) knobs[index] / 127.0f;
        return (1 - value) * min + value * max;
    }


    private static void ReadFromServer()
    {
        byte[] sockBuffer = new byte[size];

        try
        {
            while (running)
            {
                if (sock.Receive(sockBuffer, size, SocketFlags.None) > 0)
                {
                    for (int i = 0; i < size; i++)
                    {
                        knobs[i] = sockBuffer[i];
                    }
                }
                else
                {
                    Console.WriteLine("Socket connection lost; aborting");
                    sock.Shutdown(SocketShutdown.Both);
                    sock.Close();
                    break;
                }
            }
        }
        catch (SocketException e) {
            Console.WriteLine(e);
        }
    }
}